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


def test_all_sections_render(tmp_path, sample_run_data, monkeypatch):
    monkeypatch.setattr("reports.generator.REPORTS_DIR", tmp_path)
    gen = ReportGenerator()
    path = gen.generate(sample_run_data)
    html = path.read_text(encoding="utf-8")
    for i in range(1, 9):
        assert f'id="section-{i}"' in html, f"Section {i} missing"


def test_missing_fields_dont_crash(tmp_path, sample_run_data, monkeypatch):
    monkeypatch.setattr("reports.generator.REPORTS_DIR", tmp_path)
    sample_run_data["entry_low"] = None
    sample_run_data["stop_loss"] = None
    sample_run_data["target_price"] = None
    sample_run_data["pm_output"]["key_risks"] = []
    sample_run_data["pm_output"]["reasoning"] = None
    sample_run_data["pm_output"]["key_catalysts"] = []
    gen = ReportGenerator()
    path = gen.generate(sample_run_data)
    html = path.read_text(encoding="utf-8")
    assert "None" not in html
    assert "—" in html


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


def test_pm_reasoning_renders_from_real_fixture(tmp_path, monkeypatch):
    """Regression: PM reasoning from real production fixture must render in HTML.

    Locks in the contract that the PM agent's raw_output.reasoning field
    flows through build_run_data → template into Section 6 of the report.
    Catches drift if raw_output schema or template lookup ever changes.
    """
    from reports.generator import build_run_data

    monkeypatch.setattr("reports.generator.REPORTS_DIR", tmp_path)

    with open(FIXTURE_DIR / "sample_agent_outputs" / "portfolio_manager.json") as f:
        pm_result = json.load(f)

    class FakeDb:
        def get_agent_outputs(self, run_id): return []
        def get_debate_rounds(self, run_id): return []

    run_data = build_run_data(
        FakeDb(), run_id=1, ticker="AAPL",
        pm_raw_output=pm_result["raw_output"],
        bundle={}, contested=False,
    )

    expected_reasoning = pm_result["raw_output"]["reasoning"]
    assert expected_reasoning, "Fixture must have non-empty reasoning for this test to be meaningful"

    gen = ReportGenerator()
    html = gen.generate(run_data).read_text(encoding="utf-8")

    assert expected_reasoning in html, (
        "PM reasoning text from raw_output did not appear in rendered report. "
        "Check template.html Section 6 references pm_output.reasoning correctly."
    )
