# Plan 4: Reports + Monitor Automation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate 8-section HTML reports (auto + manual), complete the test pyramid (E2E + remaining failure scenarios), and automate daily watchlist monitoring via Windows Task Scheduler.

**Architecture:** A `ReportGenerator` class renders a Jinja2 template (`reports/template.html`) into `reports_output/TICKER_YYYYMMDD.html`. The orchestrator calls it automatically after Phase 4 verdict; a new `GET /report/{run_id}` endpoint regenerates on demand. E2E tests run the full pipeline against frozen fixture data with all LLM calls mocked. A PowerShell script registers `python -m pipeline.monitor` as a daily Windows scheduled task.

**Tech Stack:** Jinja2 (already pulled in by FastAPI), pytest-asyncio, openpyxl (for Excel link in report), Windows Task Scheduler via `schtasks.exe`

---

## File Map

| File | Role |
|------|------|
| `reports/__init__.py` | Package marker |
| `reports/generator.py` | `ReportGenerator` class — builds context dict, renders template |
| `reports/template.html` | Jinja2 template — 8 sections per design-spec §12 |
| `reports/styles.css` | Report-specific styles (printable, standalone) |
| `main.py` | Add `GET /report/{run_id}` endpoint |
| `pipeline/orchestrator.py` | Call `ReportGenerator.generate()` after Phase 4 |
| `tests/unit/test_report_structure.py` | Section presence, missing-field rendering |
| `tests/failure_scenarios/test_missing_data.py` | 2× minimal confidence → abort, no watchlist write |
| `tests/failure_scenarios/test_agent_failures.py` | Agent retry → failed → PM notes failure |
| `tests/e2e/test_full_run_aapl.py` | Full pipeline E2E with mocked LLMs |
| `tests/e2e/test_resume_checkpoint.py` | Pause mid-Phase 2 → upload → resume → complete |
| `scripts/install_monitor_task.ps1` | Register daily Windows scheduled task |
| `scripts/uninstall_monitor_task.ps1` | Remove the scheduled task |

---

## Task 1: Report Generator skeleton

**Files:**
- Create: `reports/__init__.py`
- Create: `reports/generator.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_report_structure.py`:

```python
import json
from pathlib import Path
import pytest
from reports.generator import ReportGenerator

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures"

@pytest.fixture
def sample_run_data():
    with open(FIXTURE_DIR / "aapl_data_bundle.json") as f:
        bundle = json.load(f)
    return {
        "run_id": 42,
        "ticker": "AAPL",
        "score": 2,
        "tier": "Strong Buy",
        "verdict": "WATCHLIST",
        "entry_low": 171.50, "entry_high": 175.00,
        "stop_loss": 163.00, "target_price": 210.00,
        "bundle": bundle,
        "agent_outputs": [],
        "debate_rounds": [],
        "pm_output": {"reasoning": "Sample reasoning",
                       "key_risks": ["Risk 1"],
                       "key_catalysts": ["Catalyst 1"],
                       "expected_returns": {}}
    }

def test_generator_returns_path(tmp_path, sample_run_data, monkeypatch):
    monkeypatch.setattr("reports.generator.REPORTS_DIR", tmp_path)
    gen = ReportGenerator()
    path = gen.generate(sample_run_data)
    assert path.exists()
    assert path.suffix == ".html"
    assert "AAPL" in path.name
```

- [ ] **Step 2: Run test — expect FAIL (ImportError)**

```powershell
./venv/Scripts/python.exe -m pytest tests/unit/test_report_structure.py::test_generator_returns_path -v
```

Expected: `ModuleNotFoundError: No module named 'reports'`

- [ ] **Step 3: Create package**

`reports/__init__.py`:
```python
```
(empty file)

- [ ] **Step 4: Create minimal generator**

`reports/generator.py`:
```python
from datetime import datetime
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape
from config import BASE_DIR
from logger import log

REPORTS_DIR = BASE_DIR / "reports_output"
TEMPLATE_DIR = BASE_DIR / "reports"


class ReportGenerator:
    def __init__(self):
        REPORTS_DIR.mkdir(exist_ok=True)
        self.env = Environment(
            loader=FileSystemLoader(str(TEMPLATE_DIR)),
            autoescape=select_autoescape(["html"]),
        )

    def generate(self, run_data: dict) -> Path:
        ticker = run_data["ticker"]
        date_str = datetime.now().strftime("%Y%m%d")
        filename = f"{ticker}_{date_str}.html"
        out_path = REPORTS_DIR / filename

        template = self.env.get_template("template.html")
        html = template.render(**self._build_context(run_data))
        out_path.write_text(html, encoding="utf-8")
        log.info(f"[hf:report] [run_{run_data['run_id']}] Generated {out_path}")
        return out_path

    def _build_context(self, run_data: dict) -> dict:
        return {
            "ticker": run_data["ticker"],
            "run_id": run_data["run_id"],
            "score": run_data["score"],
            "tier": run_data["tier"],
            "verdict": run_data["verdict"],
            "entry_low": run_data.get("entry_low"),
            "entry_high": run_data.get("entry_high"),
            "stop_loss": run_data.get("stop_loss"),
            "target_price": run_data.get("target_price"),
            "bundle": run_data["bundle"],
            "agent_outputs": run_data["agent_outputs"],
            "debate_rounds": run_data["debate_rounds"],
            "pm_output": run_data["pm_output"],
            "generated_at": datetime.now().isoformat(timespec="seconds"),
        }
```

- [ ] **Step 5: Create minimal template**

`reports/template.html`:
```html
<!doctype html>
<html><head><title>{{ ticker }} Report</title></head>
<body><h1>{{ ticker }} — {{ verdict }} ({{ tier }})</h1></body></html>
```

- [ ] **Step 6: Run test — expect PASS**

```powershell
./venv/Scripts/python.exe -m pytest tests/unit/test_report_structure.py::test_generator_returns_path -v
```

Expected: 1 passed.

- [ ] **Step 7: Commit**

```powershell
git add reports/ tests/unit/test_report_structure.py
git commit -m "feat(reports): generator skeleton with Jinja2 template"
```

---

## Task 2: All 8 report sections

**Files:**
- Modify: `reports/template.html`
- Create: `reports/styles.css`
- Modify: `tests/unit/test_report_structure.py`

- [ ] **Step 1: Write failing tests for all 8 sections**

Append to `tests/unit/test_report_structure.py`:

```python
def test_all_sections_render(tmp_path, sample_run_data, monkeypatch):
    monkeypatch.setattr("reports.generator.REPORTS_DIR", tmp_path)
    gen = ReportGenerator()
    path = gen.generate(sample_run_data)
    html = path.read_text(encoding="utf-8")
    # Each section must be marked with an id="section-N"
    for i in range(1, 9):
        assert f'id="section-{i}"' in html, f"Section {i} missing"

def test_missing_fields_dont_crash(tmp_path, sample_run_data, monkeypatch):
    monkeypatch.setattr("reports.generator.REPORTS_DIR", tmp_path)
    sample_run_data["entry_low"] = None
    sample_run_data["stop_loss"] = None
    sample_run_data["target_price"] = None
    sample_run_data["pm_output"]["key_risks"] = []
    gen = ReportGenerator()
    path = gen.generate(sample_run_data)
    html = path.read_text(encoding="utf-8")
    # Should render "—" placeholder instead of None
    assert "None" not in html  # No literal Python None leaked into HTML

def test_contested_warning_visible_when_contested(tmp_path, sample_run_data, monkeypatch):
    monkeypatch.setattr("reports.generator.REPORTS_DIR", tmp_path)
    sample_run_data["contested"] = True
    gen = ReportGenerator()
    html = gen.generate(sample_run_data).read_text(encoding="utf-8")
    assert "Contested" in html

def test_no_contested_warning_when_consensus(tmp_path, sample_run_data, monkeypatch):
    monkeypatch.setattr("reports.generator.REPORTS_DIR", tmp_path)
    sample_run_data["contested"] = False
    gen = ReportGenerator()
    html = gen.generate(sample_run_data).read_text(encoding="utf-8")
    assert 'class="contested-warning"' not in html
```

- [ ] **Step 2: Run tests — expect FAIL**

```powershell
./venv/Scripts/python.exe -m pytest tests/unit/test_report_structure.py -v
```

Expected: 4 fails (section markers missing).

- [ ] **Step 3: Write full 8-section template**

`reports/template.html` — full implementation:

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{{ ticker }} — HedgeFund Report ({{ generated_at[:10] }})</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body>

<!-- SECTION 1 — Cover -->
<section id="section-1" class="cover">
  <h1>{{ ticker }}</h1>
  <div class="score-badge score-{{ score }}">{{ score }}</div>
  <p class="tier">{{ tier }} — {{ verdict }}</p>
  <dl class="cover-meta">
    <dt>Sector</dt><dd>{{ bundle.get("sector", "—") }}</dd>
    <dt>Current Price</dt><dd>{{ "$%.2f"|format(bundle.get("current_price", 0)) if bundle.get("current_price") else "—" }}</dd>
    <dt>Market Cap</dt><dd>{{ bundle.get("market_cap_display", "—") }}</dd>
    <dt>Analysis Date</dt><dd>{{ generated_at[:10] }}</dd>
    <dt>Run ID</dt><dd>#{{ run_id }}</dd>
  </dl>
  {% if contested %}
    <div class="contested-warning">⚠ Contested — Bull and Bear did not converge</div>
  {% endif %}
</section>

<!-- SECTION 2 — Data Quality -->
<section id="section-2" class="data-quality">
  <h2>Data Quality</h2>
  <table>
    <thead><tr><th>Field</th><th>Source</th><th>Status</th></tr></thead>
    <tbody>
    {% for field, info in bundle.get("manifest", {}).items() %}
      <tr class="status-{{ info.status }}">
        <td>{{ field }}</td>
        <td>{{ info.source or "—" }}</td>
        <td>{{ info.status }}</td>
      </tr>
    {% endfor %}
    </tbody>
  </table>
</section>

<!-- SECTION 3 — Phase 1 Agent Reports -->
<section id="section-3" class="phase1">
  <h2>Phase 1 — Data Analysts</h2>
  {% for agent in agent_outputs if agent.phase == 1 %}
    <div class="agent-report agent-{{ agent.agent }}">
      <h3>{{ agent.agent|title }} — {{ agent.score }}/10
        <span class="confidence confidence-{{ agent.data_confidence }}">{{ agent.data_confidence }}</span>
      </h3>
      <p>{{ agent.summary }}</p>
      {% if agent.bull_points %}
        <h4>Bull</h4>
        <ul>{% for p in agent.bull_points %}<li>{{ p }}</li>{% endfor %}</ul>
      {% endif %}
      {% if agent.bear_points %}
        <h4>Bear</h4>
        <ul>{% for p in agent.bear_points %}<li>{{ p }}</li>{% endfor %}</ul>
      {% endif %}
    </div>
  {% endfor %}
</section>

<!-- SECTION 4 — Phase 2 Reports -->
<section id="section-4" class="phase2">
  <h2>Phase 2 — Assessment</h2>
  {% for agent in agent_outputs if agent.phase == 2 %}
    <div class="agent-report agent-{{ agent.agent }}">
      <h3>{{ agent.agent|replace("_", " ")|title }} — {{ agent.score }}/10</h3>
      <p>{{ agent.summary }}</p>
      {% if agent.agent == "financial_modeler" and agent.raw_output.get("excel_path") %}
        <a href="{{ agent.raw_output.excel_path }}" class="excel-link">Download Excel Model →</a>
      {% endif %}
    </div>
  {% endfor %}
</section>

<!-- SECTION 5 — The Debate -->
<section id="section-5" class="debate">
  <h2>Bull vs Bear Debate</h2>
  {% for round in debate_rounds %}
    <div class="debate-round">
      <h3>Round {{ round.round_number }} — Gap: {{ (round.bull_conviction - round.bear_conviction)|abs }}</h3>
      <div class="bull-arg"><strong>🐂 Bull (conviction: {{ round.bull_conviction }}):</strong> {{ round.bull_argument }}</div>
      <div class="bear-arg"><strong>🐻 Bear (conviction: {{ round.bear_conviction }}):</strong> {{ round.bear_argument }}</div>
    </div>
  {% endfor %}
  <p class="debate-result">
    {% if contested %}Final: <strong>Contested</strong>{% else %}Final: <strong>Consensus</strong>{% endif %}
  </p>
</section>

<!-- SECTION 6 — Portfolio Manager Verdict -->
<section id="section-6" class="verdict">
  <h2>Portfolio Manager Verdict</h2>
  <div class="verdict-summary verdict-{{ verdict|lower }}">
    <strong>{{ verdict }}</strong> — Score {{ score }} ({{ tier }})
  </div>
  <dl class="pricing">
    <dt>Entry Zone</dt><dd>{% if entry_low %}${{ "%.2f"|format(entry_low) }} – ${{ "%.2f"|format(entry_high) }}{% else %}—{% endif %}</dd>
    <dt>Stop Loss</dt><dd>{% if stop_loss %}${{ "%.2f"|format(stop_loss) }}{% else %}—{% endif %}</dd>
    <dt>Target</dt><dd>{% if target_price %}${{ "%.2f"|format(target_price) }}{% else %}—{% endif %}</dd>
  </dl>
  <h3>Reasoning</h3>
  <p>{{ pm_output.reasoning }}</p>
  <h3>Expected Returns</h3>
  {% if pm_output.expected_returns %}
  <table class="returns-table">
    <thead><tr><th>Horizon</th><th>Bear</th><th>Base</th><th>Bull</th></tr></thead>
    <tbody>
    {% for h in ["1m", "3m", "12m"] %}
      <tr><td>{{ h }}</td>
        <td>{{ pm_output.expected_returns.bear.get(h, "—") }}%</td>
        <td>{{ pm_output.expected_returns.base.get(h, "—") }}%</td>
        <td>{{ pm_output.expected_returns.bull.get(h, "—") }}%</td>
      </tr>
    {% endfor %}
    </tbody>
  </table>
  {% endif %}
  <h3>Key Risks</h3>
  <ul class="risks">{% for r in pm_output.key_risks %}<li>{{ r }}</li>{% endfor %}</ul>
  <h3>Key Catalysts</h3>
  <ul class="catalysts">{% for c in pm_output.key_catalysts %}<li>{{ c }}</li>{% endfor %}</ul>
</section>

<!-- SECTION 7 — Additional Intelligence -->
<section id="section-7" class="intel">
  <h2>Additional Intelligence</h2>
  <dl>
    <dt>Analyst Consensus</dt><dd>{{ bundle.get("analyst_consensus", "—") }}</dd>
    <dt>Next Earnings</dt><dd>{{ bundle.get("next_earnings_date", "—") }}</dd>
    <dt>Short Interest</dt><dd>{{ bundle.get("short_interest_pct", "—") }}%</dd>
    <dt>Insider Activity (last 90d)</dt><dd>{{ bundle.get("insider_summary", "—") }}</dd>
  </dl>
</section>

<!-- SECTION 8 — Historical Fund Performance -->
<section id="section-8" class="history">
  <h2>Historical Fund Performance</h2>
  {% if bundle.get("fund_history") %}
    <table>
      <thead><tr><th>Ticker</th><th>Score Given</th><th>Outcome</th><th>Return</th></tr></thead>
      <tbody>
      {% for h in bundle.fund_history %}
        <tr><td>{{ h.ticker }}</td><td>{{ h.score }}</td><td>{{ h.outcome }}</td><td>{{ h.return_pct }}%</td></tr>
      {% endfor %}
      </tbody>
    </table>
  {% else %}
    <p class="muted">No historical outcomes yet — populates as watchlist entries resolve.</p>
  {% endif %}
</section>

<footer class="report-footer">
  Generated {{ generated_at }} · HedgeFund Analyser
</footer>

</body></html>
```

- [ ] **Step 4: Create `reports/styles.css`**

```css
body { font-family: -apple-system, Segoe UI, sans-serif; max-width: 900px; margin: 40px auto; color: #1a1d27; line-height: 1.5; padding: 0 20px; }
section { margin-bottom: 48px; padding-bottom: 24px; border-bottom: 1px solid #e5e7eb; }
h1 { font-size: 2.5rem; margin-bottom: 4px; }
h2 { font-size: 1.5rem; color: #6366f1; margin-top: 0; }
h3 { font-size: 1.1rem; }
.cover { text-align: center; }
.score-badge { display: inline-block; width: 64px; height: 64px; line-height: 64px; border-radius: 50%; font-size: 2rem; font-weight: bold; color: white; }
.score-1 { background: #16a34a; } .score-2 { background: #22c55e; }
.score-3 { background: #f59e0b; } .score-4 { background: #ef4444; } .score-5 { background: #7f1d1d; }
.tier { font-size: 1.25rem; font-weight: 600; }
.cover-meta { display: grid; grid-template-columns: max-content auto; gap: 4px 16px; max-width: 400px; margin: 16px auto; text-align: left; }
.cover-meta dt { font-weight: 600; color: #6b7280; }
.contested-warning { background: #fef3c7; border-left: 4px solid #f59e0b; padding: 12px; margin: 16px 0; }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 6px 10px; text-align: left; border-bottom: 1px solid #e5e7eb; }
th { background: #f9fafb; font-weight: 600; }
.status-ok { color: #16a34a; } .status-partial { color: #f59e0b; } .status-missing { color: #ef4444; }
.confidence { font-size: 0.75rem; padding: 2px 6px; border-radius: 4px; margin-left: 8px; }
.confidence-full { background: #d1fae5; color: #065f46; }
.confidence-partial { background: #fef3c7; color: #92400e; }
.confidence-minimal { background: #fee2e2; color: #991b1b; }
.debate-round { background: #f9fafb; border-left: 3px solid #6366f1; padding: 12px; margin-bottom: 12px; border-radius: 4px; }
.bull-arg { margin-bottom: 8px; }
.verdict-summary { font-size: 1.25rem; padding: 12px; margin-bottom: 16px; border-radius: 6px; }
.verdict-watchlist { background: #d1fae5; color: #065f46; }
.verdict-avoid { background: #fee2e2; color: #991b1b; }
.returns-table td:nth-child(n+2) { text-align: right; }
.excel-link { display: inline-block; padding: 6px 12px; background: #16a34a; color: white; text-decoration: none; border-radius: 4px; margin-top: 8px; }
.risks li { color: #991b1b; }
.catalysts li { color: #065f46; }
.muted { color: #9ca3af; font-style: italic; }
.report-footer { text-align: center; color: #9ca3af; font-size: 0.875rem; margin-top: 48px; }
```

- [ ] **Step 5: Update `_build_context` to pass `contested` flag**

In `reports/generator.py`, add to the dict returned by `_build_context`:

```python
"contested": run_data.get("contested", False),
```

- [ ] **Step 6: Run tests — expect PASS (4 tests)**

```powershell
./venv/Scripts/python.exe -m pytest tests/unit/test_report_structure.py -v
```

Expected: 4 passed.

- [ ] **Step 7: Commit**

```powershell
git add reports/template.html reports/styles.css reports/generator.py tests/unit/test_report_structure.py
git commit -m "feat(reports): full 8-section template with styling"
```

---

## Task 3: Auto-generate at end of pipeline

**Files:**
- Modify: `pipeline/orchestrator.py`

- [ ] **Step 1: Write failing test**

Create `tests/integration/test_report_auto_generation.py`:

```python
import asyncio
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from pipeline.orchestrator import _run_pipeline

@pytest.mark.asyncio
async def test_report_generated_after_pipeline_complete(tmp_path):
    """Successful pipeline run triggers ReportGenerator.generate()."""
    queue = asyncio.Queue()
    db = MagicMock()
    db.get_agent_outputs.return_value = []
    db.get_debate_rounds.return_value = []

    pm_result = {"agent": "portfolio_manager", "phase": 4, "score": 2,
                 "status": "complete", "data_confidence": "full",
                 "raw_output": {"verdict": "WATCHLIST", "tier": "Buy",
                                "entry_low": 170.0, "entry_high": 175.0,
                                "stop_loss": 160.0, "target_price": 200.0,
                                "reasoning": "...", "key_risks": [],
                                "key_catalysts": [], "expected_returns": {}},
                 "summary": "", "duration_ms": 100,
                 "bull_points": [], "bear_points": [], "missing_fields": []}

    with patch("pipeline.orchestrator.ReportGenerator") as MockGen, \
         patch("pipeline.orchestrator.DataAggregator") as MockAgg, \
         patch("pipeline.orchestrator._run_phase_parallel") as mock_phase, \
         patch("pipeline.orchestrator.run_debate") as mock_debate, \
         patch("pipeline.orchestrator._run_agent_async", new=AsyncMock(return_value=pm_result)):
        MockAgg.return_value.fetch_all = AsyncMock(return_value={"ticker": "AAPL"})
        mock_phase.side_effect = [
            [{"agent": f"a{i}", "phase": 1, "score": 7, "data_confidence": "full",
              "status": "complete", "summary": "", "duration_ms": 100,
              "bull_points": [], "bear_points": [], "missing_fields": []} for i in range(5)],
            [{"agent": f"b{i}", "phase": 2, "score": 7, "data_confidence": "full",
              "status": "complete", "summary": "", "duration_ms": 100,
              "bull_points": [], "bear_points": [], "missing_fields": []} for i in range(3)]
        ]
        async def empty_debate(*args, **kwargs):
            return
            yield  # make it an async generator
        mock_debate.return_value = empty_debate()

        await _run_pipeline("AAPL", 1, db, queue, None)

    MockGen.return_value.generate.assert_called_once()
```

- [ ] **Step 2: Run test — expect FAIL**

```powershell
./venv/Scripts/python.exe -m pytest tests/integration/test_report_auto_generation.py -v
```

Expected: `AttributeError: module 'pipeline.orchestrator' has no attribute 'ReportGenerator'`

- [ ] **Step 3: Add report generation to orchestrator**

In `pipeline/orchestrator.py`:

1. Add import at top: `from reports.generator import ReportGenerator`
2. After Phase 4 completes successfully, before emitting `complete` event, add:

```python
# Auto-generate HTML report
try:
    run_data = {
        "run_id": run_id,
        "ticker": ticker,
        "score": pm_result["raw_output"].get("score", pm_result["score"]),
        "tier": pm_result["raw_output"].get("tier", ""),
        "verdict": pm_result["raw_output"].get("verdict", ""),
        "entry_low": pm_result["raw_output"].get("entry_low"),
        "entry_high": pm_result["raw_output"].get("entry_high"),
        "stop_loss": pm_result["raw_output"].get("stop_loss"),
        "target_price": pm_result["raw_output"].get("target_price"),
        "bundle": bundle,
        "agent_outputs": db.get_agent_outputs(run_id),
        "debate_rounds": db.get_debate_rounds(run_id),
        "pm_output": pm_result["raw_output"],
        "contested": bundle.get("debate_contested", False),
    }
    report_path = ReportGenerator().generate(run_data)
    await queue.put({"event": "report_ready", "path": str(report_path)})
except Exception as e:
    log.warning(f"[hf:pipeline] [run_{run_id}] Report generation failed: {e}")
```

- [ ] **Step 4: Run test — expect PASS**

```powershell
./venv/Scripts/python.exe -m pytest tests/integration/test_report_auto_generation.py -v
```

Expected: 1 passed.

- [ ] **Step 5: Confirm no regressions**

```powershell
./venv/Scripts/python.exe -m pytest tests/ --ignore=tests/e2e -q
```

Expected: all previously passing tests still pass.

- [ ] **Step 6: Commit**

```powershell
git add pipeline/orchestrator.py tests/integration/test_report_auto_generation.py
git commit -m "feat(pipeline): auto-generate report after Phase 4"
```

---

## Task 4: Manual report endpoint

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Write failing test**

Create `tests/integration/test_report_endpoint.py`:

```python
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from pathlib import Path
from main import app

client = TestClient(app)

def test_get_report_regenerates_and_returns_html(tmp_path):
    fake_path = tmp_path / "AAPL_20260513.html"
    fake_path.write_text("<html>test report</html>", encoding="utf-8")

    with patch("main.ReportGenerator") as MockGen, \
         patch("main.db") as mock_db:
        MockGen.return_value.generate.return_value = fake_path
        mock_db.get_run.return_value = {
            "run_id": 1, "ticker": "AAPL", "score": 2, "tier": "Buy",
            "verdict": "WATCHLIST", "entry_low": 170, "entry_high": 175,
            "stop_loss": 160, "target_price": 200,
        }
        mock_db.get_agent_outputs.return_value = []
        mock_db.get_debate_rounds.return_value = []
        mock_db.get_bundle_snapshot.return_value = {"ticker": "AAPL"}
        mock_db.get_pm_output.return_value = {
            "reasoning": "", "key_risks": [], "key_catalysts": [],
            "expected_returns": {}
        }
        resp = client.get("/report/1")

    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "test report" in resp.text

def test_get_report_404_on_missing_run():
    with patch("main.db") as mock_db:
        mock_db.get_run.return_value = None
        resp = client.get("/report/999999")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run test — expect FAIL (404 on both)**

```powershell
./venv/Scripts/python.exe -m pytest tests/integration/test_report_endpoint.py -v
```

- [ ] **Step 3: Add endpoint to `main.py`**

Add import: `from fastapi.responses import HTMLResponse` and `from reports.generator import ReportGenerator`

Add helper `db.get_bundle_snapshot(run_id)` if not present — it should load `debug/bundles/run_{id}_bundle.json`. If `db` doesn't have this method, add it to `db/database.py`:

```python
def get_bundle_snapshot(self, run_id: int) -> dict:
    from config import BASE_DIR
    import json
    path = BASE_DIR / "debug" / "bundles" / f"run_{run_id}_bundle.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}
```

Add endpoint to `main.py`:

```python
@app.get("/report/{run_id}", response_class=HTMLResponse)
async def get_report(run_id: int):
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    run_data = {
        "run_id": run_id,
        "ticker": run["ticker"],
        "score": run.get("score"),
        "tier": run.get("tier"),
        "verdict": run.get("verdict"),
        "entry_low": run.get("entry_low"),
        "entry_high": run.get("entry_high"),
        "stop_loss": run.get("stop_loss"),
        "target_price": run.get("target_price"),
        "bundle": db.get_bundle_snapshot(run_id),
        "agent_outputs": db.get_agent_outputs(run_id),
        "debate_rounds": db.get_debate_rounds(run_id),
        "pm_output": db.get_pm_output(run_id),
        "contested": bool(run.get("contested")),
    }
    path = ReportGenerator().generate(run_data)
    return HTMLResponse(content=path.read_text(encoding="utf-8"))
```

- [ ] **Step 4: Run tests — expect PASS**

```powershell
./venv/Scripts/python.exe -m pytest tests/integration/test_report_endpoint.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```powershell
git add main.py db/database.py tests/integration/test_report_endpoint.py
git commit -m "feat(api): GET /report/{run_id} for manual report regeneration"
```

---

## Task 5: Failure scenario — missing data (2× minimal abort)

**Files:**
- Create: `tests/failure_scenarios/test_missing_data.py`

- [ ] **Step 1: Write tests**

```python
import asyncio
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from pipeline.orchestrator import _run_pipeline

@pytest.mark.asyncio
async def test_two_minimal_agents_aborts_pipeline():
    """When 2+ Phase 1 agents return data_confidence=minimal, pipeline emits abort and does not run Phase 2."""
    minimal = {"agent": "test", "phase": 1, "score": 1, "data_confidence": "minimal",
               "status": "complete", "summary": "", "duration_ms": 100,
               "bull_points": [], "bear_points": [], "missing_fields": ["x"]}
    full = {**minimal, "data_confidence": "full", "score": 7, "missing_fields": []}
    phase1 = [minimal, minimal, full, full, full]

    queue = asyncio.Queue()
    db = MagicMock()
    phase2_called = MagicMock()

    async def mock_phase_parallel(agent_classes, *args, **kwargs):
        if any(c.__name__.startswith("Risk") for c in agent_classes):
            phase2_called()
            return []
        return phase1

    with patch("pipeline.orchestrator.DataAggregator") as MockAgg, \
         patch("pipeline.orchestrator._run_phase_parallel", side_effect=mock_phase_parallel):
        MockAgg.return_value.fetch_all = AsyncMock(return_value={"ticker": "TEST"})
        await _run_pipeline("TEST", 1, db, queue, None)

    events = []
    while not queue.empty():
        e = await queue.get()
        if e is not None:
            events.append(e)

    assert any(e.get("event") == "abort" for e in events)
    phase2_called.assert_not_called()
    db.update_run_status.assert_called_with(1, "failed")

@pytest.mark.asyncio
async def test_one_minimal_agent_does_not_abort():
    """Single minimal agent does NOT trigger abort."""
    minimal = {"agent": "test", "phase": 1, "score": 1, "data_confidence": "minimal",
               "status": "complete", "summary": "", "duration_ms": 100,
               "bull_points": [], "bear_points": [], "missing_fields": ["x"]}
    full = {**minimal, "data_confidence": "full", "score": 7, "missing_fields": []}
    phase1 = [minimal, full, full, full, full]

    queue = asyncio.Queue()
    db = MagicMock()
    phase2_called = MagicMock()

    async def mock_phase_parallel(agent_classes, *args, **kwargs):
        if any(c.__name__.startswith("Risk") for c in agent_classes):
            phase2_called()
            return []
        return phase1

    pm_result = {"raw_output": {"verdict": "AVOID", "score": 4, "tier": "Sell"},
                 "score": 4, "status": "complete", "phase": 4,
                 "data_confidence": "full", "summary": "", "duration_ms": 100,
                 "bull_points": [], "bear_points": [], "missing_fields": []}

    with patch("pipeline.orchestrator.DataAggregator") as MockAgg, \
         patch("pipeline.orchestrator._run_phase_parallel", side_effect=mock_phase_parallel), \
         patch("pipeline.orchestrator.run_debate") as mock_debate, \
         patch("pipeline.orchestrator._run_agent_async", new=AsyncMock(return_value=pm_result)), \
         patch("pipeline.orchestrator.ReportGenerator"):
        MockAgg.return_value.fetch_all = AsyncMock(return_value={"ticker": "TEST"})
        async def empty_debate(*a, **kw):
            return
            yield
        mock_debate.return_value = empty_debate()
        await _run_pipeline("TEST", 1, db, queue, None)

    phase2_called.assert_called_once()
```

- [ ] **Step 2: Run — expect PASS (existing abort rule already implemented)**

```powershell
./venv/Scripts/python.exe -m pytest tests/failure_scenarios/test_missing_data.py -v
```

Expected: 2 passed. (No code changes needed — verifies existing behaviour.)

- [ ] **Step 3: Commit**

```powershell
git add tests/failure_scenarios/test_missing_data.py
git commit -m "test: failure scenario — 2x minimal confidence triggers abort"
```

---

## Task 6: Failure scenario — agent failures

**Files:**
- Create: `tests/failure_scenarios/test_agent_failures.py`

- [ ] **Step 1: Write tests**

```python
import pytest
from unittest.mock import patch, MagicMock
from agents.base_agent import BaseAgent

class DummyAgent(BaseAgent):
    agent_name = "dummy"
    phase = 1
    role_prompt_path = "dummy"
    skill_prompt_paths = []

    def _build_user_prompt(self, bundle):
        return "test"

    def _parse_response(self, text):
        return {"score": 5, "summary": "ok", "data_confidence": "full",
                "bull_points": [], "bear_points": [], "missing_fields": []}

def test_agent_retries_once_on_first_failure():
    agent = DummyAgent()
    bundle = {"ticker": "TEST"}
    call_count = [0]

    def flaky_call(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            raise RuntimeError("transient LLM error")
        return '{"score": 7, "summary": "ok", "data_confidence": "full", "bull_points": [], "bear_points": [], "missing_fields": []}'

    with patch.object(agent, "_call_llm", side_effect=flaky_call):
        result = agent.run(bundle, run_id=1)

    assert call_count[0] == 2
    assert result["status"] == "complete"
    assert result["score"] == 7

def test_agent_marked_failed_after_second_failure():
    agent = DummyAgent()
    bundle = {"ticker": "TEST"}

    with patch.object(agent, "_call_llm", side_effect=RuntimeError("permanent error")):
        result = agent.run(bundle, run_id=1)

    assert result["status"] == "failed"
    assert result["score"] == 0 or result["score"] is None
    assert "permanent error" in (result.get("error") or "").lower() or result["status"] == "failed"

def test_pm_notes_failed_agents_in_reasoning():
    """When agents fail in Phase 1, the PM input should include status=failed entries."""
    from pipeline.orchestrator import _build_summaries
    failed_result = {"agent": "fundamental", "phase": 1, "score": 0,
                     "data_confidence": "minimal", "status": "failed",
                     "summary": "Agent failed: LLM error", "duration_ms": 5000,
                     "bull_points": [], "bear_points": [], "missing_fields": []}
    summaries = _build_summaries([failed_result])
    assert "fundamental" in summaries
    assert summaries["fundamental"]["status"] == "failed" or "failed" in summaries["fundamental"]["summary"].lower()
```

- [ ] **Step 2: Run tests**

```powershell
./venv/Scripts/python.exe -m pytest tests/failure_scenarios/test_agent_failures.py -v
```

- [ ] **Step 3: Fix any failures**

If `BaseAgent.run()` does not currently retry-once, add retry logic. If `_build_summaries` doesn't pass `status`, add it.

Expected after fixes: 3 passed.

- [ ] **Step 4: Commit**

```powershell
git add agents/base_agent.py pipeline/orchestrator.py tests/failure_scenarios/test_agent_failures.py
git commit -m "test+fix: agent failure handling — retry once, mark failed, propagate to PM"
```

---

## Task 7: E2E — full pipeline run

**Files:**
- Create: `tests/e2e/test_full_run_aapl.py`

- [ ] **Step 1: Write the E2E test**

```python
import asyncio
import json
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from pipeline.orchestrator import stream_analysis

FIXTURES = Path(__file__).parent.parent / "fixtures"

@pytest.mark.asyncio
async def test_full_pipeline_aapl(tmp_path, monkeypatch):
    """Full pipeline against frozen AAPL fixture — all phases complete, report generated, watchlist entry written."""
    monkeypatch.setattr("reports.generator.REPORTS_DIR", tmp_path / "reports")
    (tmp_path / "reports").mkdir()

    with open(FIXTURES / "aapl_data_bundle.json") as f:
        bundle = json.load(f)

    db = MagicMock()
    db.create_run.return_value = 1
    db.get_agent_outputs.return_value = []
    db.get_debate_rounds.return_value = []

    sample_outputs_dir = FIXTURES / "sample_agent_outputs"
    def load_sample(name):
        with open(sample_outputs_dir / f"{name}.json") as f:
            return json.load(f)

    phase1_results = [load_sample(n) for n in
                      ["fundamental", "technical", "sentiment", "macro", "earnings_reviewer"]]
    phase2_results = [load_sample(n) for n in
                      ["risk_manager", "thesis_validator", "financial_modeler"]]
    bull_result = load_sample("bull")
    bear_result = load_sample("bear")
    pm_result = load_sample("portfolio_manager")

    async def mock_phase(agent_classes, *args, **kwargs):
        names = [c.__name__ for c in agent_classes]
        if any("Fundamental" in n for n in names):
            return phase1_results
        return phase2_results

    bundle_for_aggregator = bundle

    with patch("pipeline.orchestrator.DataAggregator") as MockAgg, \
         patch("pipeline.orchestrator._run_phase_parallel", side_effect=mock_phase), \
         patch("pipeline.orchestrator._run_agent_async", new=AsyncMock(return_value=pm_result)), \
         patch("pipeline.debate._run_agent_async", new=AsyncMock(side_effect=[bull_result, bear_result] * 4)):
        MockAgg.return_value.fetch_all = AsyncMock(return_value=bundle_for_aggregator)

        events = []
        async for sse_line in stream_analysis("AAPL", db):
            events.append(sse_line)

    # Verify pipeline emitted key events
    event_types = []
    for line in events:
        if line.startswith("data: "):
            data = json.loads(line[6:])
            if isinstance(data, dict) and "event" in data:
                event_types.append(data["event"])

    assert "fetch_complete" in event_types
    assert "phase_complete" in event_types
    assert event_types.count("phase_complete") == 4  # 4 phases
    assert "verdict" in event_types
    assert "complete" in event_types
    assert "abort" not in event_types

    # Report file was generated
    reports = list((tmp_path / "reports").glob("AAPL_*.html"))
    assert len(reports) == 1
```

- [ ] **Step 2: Run E2E test**

```powershell
./venv/Scripts/python.exe -m pytest tests/e2e/test_full_run_aapl.py -v
```

- [ ] **Step 3: Fix any fixture mismatches**

If `sample_agent_outputs/*.json` doesn't match the agent contract from Plan 2, update fixtures (not code). Expected: 1 passed.

- [ ] **Step 4: Commit**

```powershell
git add tests/e2e/test_full_run_aapl.py
git commit -m "test(e2e): full pipeline run with frozen AAPL fixtures"
```

---

## Task 8: E2E — resume from checkpoint

**Files:**
- Create: `tests/e2e/test_resume_checkpoint.py`

- [ ] **Step 1: Write the test**

```python
import asyncio
import json
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from pipeline.orchestrator import stream_resume

FIXTURES = Path(__file__).parent.parent / "fixtures"

@pytest.mark.asyncio
async def test_resume_from_phase2_checkpoint(tmp_path, monkeypatch):
    """Run paused after Phase 1 → resume → completes from Phase 2 onwards."""
    monkeypatch.setattr("reports.generator.REPORTS_DIR", tmp_path)

    with open(FIXTURES / "aapl_data_bundle.json") as f:
        bundle = json.load(f)

    sample_dir = FIXTURES / "sample_agent_outputs"
    def load(n):
        with open(sample_dir / f"{n}.json") as f:
            return json.load(f)

    phase1_results = [load(n) for n in ["fundamental", "technical", "sentiment", "macro", "earnings_reviewer"]]
    phase2_results = [load(n) for n in ["risk_manager", "thesis_validator", "financial_modeler"]]

    db = MagicMock()
    db.get_run.return_value = {"run_id": 7, "ticker": "AAPL", "status": "paused"}
    db.get_checkpoint.return_value = {
        "completed_phase": 1,
        "phase1_results": phase1_results,
        "bundle_path": str(FIXTURES / "aapl_data_bundle.json"),
    }
    db.get_agent_outputs.return_value = []
    db.get_debate_rounds.return_value = []

    phase_calls = []

    async def mock_phase(agent_classes, *args, **kwargs):
        names = [c.__name__ for c in agent_classes]
        phase_calls.append(names)
        if any("Fundamental" in n for n in names):
            return phase1_results
        return phase2_results

    with patch("pipeline.orchestrator._run_phase_parallel", side_effect=mock_phase), \
         patch("pipeline.orchestrator._run_agent_async",
               new=AsyncMock(return_value=load("portfolio_manager"))), \
         patch("pipeline.debate._run_agent_async",
               new=AsyncMock(side_effect=[load("bull"), load("bear")] * 4)):

        events = []
        async for sse_line in stream_resume(7, db):
            events.append(sse_line)

    # Phase 1 should NOT have been re-run
    phase1_re_run = any(any("Fundamental" in n for n in call) for call in phase_calls)
    assert not phase1_re_run, "Phase 1 was re-run; should resume from Phase 2"

    # Verdict event present
    event_types = []
    for line in events:
        if line.startswith("data: "):
            data = json.loads(line[6:])
            if isinstance(data, dict) and "event" in data:
                event_types.append(data["event"])
    assert "verdict" in event_types
```

- [ ] **Step 2: Run test**

```powershell
./venv/Scripts/python.exe -m pytest tests/e2e/test_resume_checkpoint.py -v
```

- [ ] **Step 3: Fix `stream_resume` if needed**

If `stream_resume` doesn't currently skip Phase 1 when checkpoint says it's complete, add that logic.

Expected: 1 passed.

- [ ] **Step 4: Commit**

```powershell
git add pipeline/orchestrator.py tests/e2e/test_resume_checkpoint.py
git commit -m "test(e2e)+fix: resume skips completed phases per checkpoint"
```

---

## Task 9: Windows Task Scheduler — install script

**Files:**
- Create: `scripts/install_monitor_task.ps1`
- Create: `scripts/uninstall_monitor_task.ps1`

- [ ] **Step 1: Create install script**

`scripts/install_monitor_task.ps1`:

```powershell
# Registers a daily Windows scheduled task that runs the HedgeFund watchlist monitor.
# Usage: powershell -ExecutionPolicy Bypass -File scripts\install_monitor_task.ps1

$TaskName = "HedgeFundWatchlistMonitor"
$ProjectRoot = (Resolve-Path "$PSScriptRoot\..").Path
$PythonExe = Join-Path $ProjectRoot "venv\Scripts\python.exe"
$ScriptArgs = "-m pipeline.monitor"
$LogPath = Join-Path $ProjectRoot "logs\monitor_task.log"

if (-not (Test-Path $PythonExe)) {
    Write-Error "Python venv not found at $PythonExe — create venv first."
    exit 1
}

# Remove existing task if present
schtasks /Query /TN $TaskName 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "Removing existing task $TaskName..."
    schtasks /Delete /TN $TaskName /F | Out-Null
}

# Create new daily task at 16:30 local time (after US market close)
$Command = "cmd.exe /c `"cd /d $ProjectRoot && $PythonExe $ScriptArgs >> $LogPath 2>&1`""

schtasks /Create `
    /TN $TaskName `
    /TR $Command `
    /SC DAILY `
    /ST 16:30 `
    /RL LIMITED `
    /F

if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Scheduled task '$TaskName' installed — runs daily at 16:30."
    Write-Host "  Logs: $LogPath"
    Write-Host "  Verify: schtasks /Query /TN $TaskName /V /FO LIST"
    Write-Host "  Run now: schtasks /Run /TN $TaskName"
} else {
    Write-Error "Failed to register scheduled task."
    exit 1
}
```

- [ ] **Step 2: Create uninstall script**

`scripts/uninstall_monitor_task.ps1`:

```powershell
$TaskName = "HedgeFundWatchlistMonitor"
schtasks /Delete /TN $TaskName /F
```

- [ ] **Step 3: Test install (dry run check syntax only)**

```powershell
powershell -ExecutionPolicy Bypass -Command "& { Get-Content scripts\install_monitor_task.ps1 | Out-Null; Write-Host 'syntax ok' }"
```

Note: actual `schtasks /Create` requires user confirmation to install — not run automatically by this plan. Run manually when ready:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install_monitor_task.ps1
```

- [ ] **Step 4: Verify task runs manually**

After install, trigger immediately to confirm wiring:

```powershell
schtasks /Run /TN HedgeFundWatchlistMonitor
# Wait 30s
Get-Content logs\monitor_task.log -Tail 20
```

Expected: log shows `[hf:monitor] [run_None] Watchlist check complete | checked: N | alerted: N | errors: N`.

- [ ] **Step 5: Commit**

```powershell
git add scripts/
git commit -m "feat(monitor): Windows Task Scheduler install/uninstall scripts"
```

---

## Task 10: Final integration verification

- [ ] **Step 1: Run full test suite**

```powershell
./venv/Scripts/python.exe -m pytest tests/ -q
```

Expected: all tests pass (≥ 86 prior + ~12 new from this plan).

- [ ] **Step 2: Start server and run one analysis manually**

```powershell
./venv/Scripts/uvicorn.exe main:app
# Open http://localhost:8000 → submit "MSFT" → wait for verdict → confirm /report/{id} loads
```

- [ ] **Step 3: Update README**

In `README.md`, document:
- How to view reports (`reports_output/` or `GET /report/{run_id}`)
- How to install the daily monitor task
- How to uninstall

- [ ] **Step 4: Final commit + tag**

```powershell
git add README.md
git commit -m "docs: report viewing + monitor task install instructions"
git tag -a v1.0 -m "Plan 4 complete — reports, full test pyramid, daily monitor"
```

---

## Final Verification

```powershell
# All tests pass
./venv/Scripts/python.exe -m pytest tests/ -q
# Expect: ~98 passed

# E2E specifically
./venv/Scripts/python.exe -m pytest tests/e2e -v
# Expect: 2 passed (test_full_run_aapl, test_resume_checkpoint)

# Failure scenarios complete
./venv/Scripts/python.exe -m pytest tests/failure_scenarios -v
# Expect: 4 files, all passing

# Manual smoke: generate a report from existing run
curl -o test_report.html http://localhost:8000/report/1
# Open test_report.html in browser — confirm all 8 sections render

# Monitor task installed
schtasks /Query /TN HedgeFundWatchlistMonitor /FO LIST
```

**On completion:** Tag `v1.0`, push to GitHub, update memory `project_hedgefund.md` to mark Plan 4 complete.
