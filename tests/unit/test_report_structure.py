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
