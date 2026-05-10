# tests/unit/test_data_manifest.py
from data.manifest import ManifestBuilder, DataConfidence


def test_all_ok_returns_full_confidence():
    b = ManifestBuilder()
    b.add("revenue", 1_000_000, source="alpha_vantage", status="ok")
    b.add("pe_ratio", 28.5, source="massive_market", status="ok")
    assert b.confidence() == DataConfidence.FULL


def test_one_non_critical_missing_returns_partial():
    b = ManifestBuilder()
    b.add("revenue", 1_000_000, source="alpha_vantage", status="ok")
    b.add("options_pcr", None, source=None, status="missing")  # non-critical
    assert b.confidence() == DataConfidence.PARTIAL


def test_critical_field_missing_returns_minimal():
    b = ManifestBuilder()
    b.add("revenue", None, source=None, status="missing", critical=True)
    b.add("pe_ratio", 28.5, source="massive_market", status="ok")
    assert b.confidence() == DataConfidence.MINIMAL


def test_to_dict_contains_all_fields():
    b = ManifestBuilder()
    b.add("revenue", 1_000_000, source="alpha_vantage", status="ok")
    b.add("revenue_growth", None, source=None, status="missing", note="API returned empty")
    d = b.to_dict()
    assert d["revenue"]["value"] == 1_000_000
    assert d["revenue"]["status"] == "ok"
    assert d["revenue_growth"]["status"] == "missing"
    assert d["revenue_growth"]["note"] == "API returned empty"


def test_partial_status_carries_note():
    b = ManifestBuilder()
    b.add("news", [{"title": "x"}], source="massive_market", status="partial",
          note="3 articles, expected 20")
    d = b.to_dict()
    assert d["news"]["status"] == "partial"
    assert "3 articles" in d["news"]["note"]
