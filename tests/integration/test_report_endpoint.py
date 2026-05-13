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
