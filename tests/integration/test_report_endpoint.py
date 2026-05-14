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


def test_get_report_409_on_run_without_verdict():
    """Running/paused/aborted runs (no verdict yet) → 409, not garbage HTML."""
    for status in ("pending", "running", "paused", "failed"):
        with patch("main.db") as mock_db:
            mock_db.get_run.return_value = {
                "run_id": 1, "ticker": "AAPL", "status": status, "verdict": None,
            }
            resp = client.get("/report/1")
        assert resp.status_code == 409, (
            f"Expected 409 for status={status!r} with no verdict, got {resp.status_code}"
        )
        assert "verdict" in resp.json()["detail"].lower()


def test_get_report_200_on_failed_run_with_avoid_verdict():
    """A failed run that still has a verdict (e.g. AVOID) is reportable."""
    fake_path = Path(__file__).parent / "_tmp_avoid.html"
    fake_path.write_text("<html>avoid report</html>", encoding="utf-8")
    try:
        with patch("main.ReportGenerator") as MockGen, \
             patch("main.db") as mock_db:
            MockGen.return_value.generate.return_value = fake_path
            mock_db.get_run.return_value = {
                "run_id": 2, "ticker": "MSFT", "status": "failed",
                "verdict": "avoid", "score": 4, "tier": "Sell",
            }
            mock_db.get_agent_outputs.return_value = []
            mock_db.get_debate_rounds.return_value = []
            mock_db.get_bundle_snapshot.return_value = {"ticker": "MSFT"}
            mock_db.get_pm_output.return_value = {"reasoning": "", "key_risks": [],
                                                    "key_catalysts": [], "expected_returns": {}}
            resp = client.get("/report/2")
        assert resp.status_code == 200
        assert "avoid report" in resp.text
    finally:
        if fake_path.exists():
            fake_path.unlink()
