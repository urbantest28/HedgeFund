import pytest
from unittest.mock import patch, MagicMock
from data.insider_client import InsiderClient

# Realistic OpenInsider CSV format.
# Columns (0-indexed): X, Filing Date, Trade Date, Ticker, Insider Name,
#                      Title, Trade Type, Price, Qty, Owned, ΔOwn, Value
SAMPLE_CSV = (
    "X,Filing Date,Trade Date,Ticker,Insider Name,Title,"
    "Trade Type,Price,Qty,Owned,ΔOwn,Value\n"
    " ,2026-05-01,2026-04-30,AAPL,Cook Timothy D,Chief Exec. Officer,"
    'P - Purchase,"$183.50","5,000","1,000,000",+0.50%,"$917,500"\n'
    " ,2026-04-15,2026-04-14,AAPL,Williams Jeffrey E,COO,"
    'S - Sale,"$180.00","2,000","500,000",-0.40%,"$360,000"\n'
)


def _mock_response(ok: bool, text: str = "") -> MagicMock:
    r = MagicMock()
    r.ok = ok
    r.text = text
    return r


def test_get_transactions_returns_correct_structure():
    client = InsiderClient()
    with patch("data.insider_client.requests.get",
               return_value=_mock_response(True, SAMPLE_CSV)):
        result = client.get_transactions("AAPL", days=90)
    assert result["source"] == "openinsider"
    assert isinstance(result["transactions"], list)
    assert len(result["transactions"]) == 2


def test_get_transactions_parses_buy_correctly():
    client = InsiderClient()
    with patch("data.insider_client.requests.get",
               return_value=_mock_response(True, SAMPLE_CSV)):
        result = client.get_transactions("AAPL")
    buy = result["transactions"][0]
    assert buy["transaction_type"] == "buy"
    assert buy["officer_name"] == "Cook Timothy D"
    assert buy["title"] == "Chief Exec. Officer"
    assert buy["date"] == "2026-05-01"
    assert buy["shares"] == 5000
    assert abs(buy["price_per_share"] - 183.50) < 0.01
    assert abs(buy["value"] - 917500.0) < 1.0


def test_get_transactions_parses_sell_correctly():
    client = InsiderClient()
    with patch("data.insider_client.requests.get",
               return_value=_mock_response(True, SAMPLE_CSV)):
        result = client.get_transactions("AAPL")
    sell = result["transactions"][1]
    assert sell["transaction_type"] == "sell"
    assert sell["shares"] == 2000


def test_get_transactions_empty_on_http_error():
    client = InsiderClient()
    with patch("data.insider_client.requests.get",
               return_value=_mock_response(False)):
        result = client.get_transactions("AAPL")
    assert result["transactions"] == []
    assert result["source"] == "openinsider"
    assert "error" not in result


def test_get_transactions_empty_on_exception():
    client = InsiderClient()
    with patch("data.insider_client.requests.get",
               side_effect=Exception("connection timeout")):
        result = client.get_transactions("AAPL")
    assert result["transactions"] == []
    assert "error" in result


def test_get_transactions_skips_malformed_rows():
    bad_csv = (
        "X,Filing Date,Trade Date,Ticker,Insider Name,Title,"
        "Trade Type,Price,Qty,Owned,ΔOwn,Value\n"
        " ,bad,row\n"  # too short, should be skipped
        " ,2026-05-01,2026-04-30,AAPL,Cook Timothy D,CEO,"
        'P - Purchase,"$183.50","5,000","1,000,000",+0.50%,"$917,500"\n'
    )
    client = InsiderClient()
    with patch("data.insider_client.requests.get",
               return_value=_mock_response(True, bad_csv)):
        result = client.get_transactions("AAPL")
    assert len(result["transactions"]) == 1
