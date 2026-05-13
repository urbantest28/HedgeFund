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
