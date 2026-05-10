import pytest
import json
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / "fixtures"

@pytest.fixture
def aapl_bundle():
    """Frozen AAPL data bundle — all tests use this, no real API calls."""
    with open(FIXTURES_DIR / "aapl_data_bundle.json") as f:
        return json.load(f)
