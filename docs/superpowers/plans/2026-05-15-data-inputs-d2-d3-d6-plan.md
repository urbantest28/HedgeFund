# Data & Inputs Expansion (D2, D3, D6) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add three new free data signals — expanded FRED macro indicators (PCE + yield curve), insider Form 4 transactions via OpenInsider, and short interest from yfinance — wiring each into the relevant agent prompt.

**Architecture:** Each data signal is implemented bottom-up: client → aggregator → prompt. D6 (short interest) is zero-cost — it extracts fields already fetched inside `get_fundamentals()`. D2 (FRED) adds two series to the existing `get_macro_snapshot()`. D3 (insider) adds a new `InsiderClient` that calls the free OpenInsider CSV endpoint. The aggregator and orchestrator receive one new constructor argument (`insider`).

**Tech Stack:** Python 3.9, `requests` (already installed), `csv` (stdlib), `fredapi` (already installed), `yfinance` (already installed), `pytest` + `unittest.mock` for tests.

---

## File Map

| File | Change |
|------|--------|
| `data/yfinance_client.py` | Add `short_interest` dict to `get_fundamentals()` return |
| `data/fred_client.py` | Add `pce` and `yield_curve_spread` to `get_macro_snapshot()` |
| `data/insider_client.py` | **New** — `InsiderClient` with `get_transactions()` |
| `data/aggregator.py` | Add `insider` param, insider fetch block, short interest manifest entry |
| `pipeline/orchestrator.py` | Import + instantiate `InsiderClient`, pass to `DataAggregator` |
| `prompts/roles/macro_analyst.md` | Add PCE/yield curve fields and responsibility bullet |
| `prompts/roles/fundamental_analyst.md` | Add insider activity field and responsibility bullet |
| `prompts/roles/technical_analyst.md` | Add short interest field and responsibility bullet |
| `tests/unit/test_yfinance_short_interest.py` | **New** — unit tests for short interest extraction |
| `tests/unit/test_insider_client.py` | **New** — unit tests for `InsiderClient` |
| `tests/integration/test_fred_client.py` | Extend existing tests to cover PCE + yield curve |
| `tests/integration/test_aggregator.py` | Update `mock_clients` fixture + add insider/short interest tests |

---

## Task 1: D6 — Extract short interest from yfinance

**Files:**
- Create: `tests/unit/test_yfinance_short_interest.py`
- Modify: `data/yfinance_client.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_yfinance_short_interest.py`:

```python
import pytest
from unittest.mock import patch, MagicMock
from data.yfinance_client import YFinanceClient


def _make_client_with_info(info: dict) -> YFinanceClient:
    with patch("data.yfinance_client.yf.Ticker") as mock_ticker:
        mock_ticker.return_value.info = info
        client = YFinanceClient()
        result = client.get_fundamentals("AAPL")
    return result


def test_get_fundamentals_includes_short_interest_fields():
    info = {
        "trailingPE": 28.5,
        "shortPercentOfFloat": 0.043,
        "shortRatio": 2.1,
        "sharesShort": 95_000_000,
    }
    result = _make_client_with_info(info)
    assert "short_interest" in result
    assert result["short_interest"]["short_float_pct"] == 0.043
    assert result["short_interest"]["days_to_cover"] == 2.1
    assert result["short_interest"]["shares_short"] == 95_000_000


def test_get_fundamentals_short_interest_null_when_missing():
    info = {"trailingPE": 28.5}  # no short interest fields
    result = _make_client_with_info(info)
    assert result["short_interest"]["short_float_pct"] is None
    assert result["short_interest"]["days_to_cover"] is None
    assert result["short_interest"]["shares_short"] is None


def test_get_fundamentals_error_includes_short_interest_null():
    with patch("data.yfinance_client.yf.Ticker", side_effect=Exception("timeout")):
        client = YFinanceClient()
        result = client.get_fundamentals("AAPL")
    assert "short_interest" in result
    assert result["short_interest"]["short_float_pct"] is None
```

- [ ] **Step 2: Run to confirm tests fail**

```
pytest tests/unit/test_yfinance_short_interest.py -v
```
Expected: `FAILED` — `KeyError: 'short_interest'`

- [ ] **Step 3: Implement short interest extraction in `data/yfinance_client.py`**

In `get_fundamentals()`, add `short_interest` to the return dict (after `"name"`):

```python
def get_fundamentals(self, ticker: str) -> dict:
    try:
        info = yf.Ticker(ticker).info
        return {
            "pe_ratio":       info.get("trailingPE"),
            "price_to_book":  info.get("priceToBook"),
            "ev_ebitda":      info.get("enterpriseToEbitda"),
            "price_to_sales": info.get("priceToSalesTrailing12Months"),
            "roe":            info.get("returnOnEquity"),
            "debt_equity":    info.get("debtToEquity"),
            "revenue_growth": info.get("revenueGrowth"),
            "gross_margin":   info.get("grossMargins"),
            "market_cap":     info.get("marketCap"),
            "sector":         info.get("sector"),
            "industry":       info.get("industry"),
            "name":           info.get("shortName"),
            "short_interest": {
                "short_float_pct": info.get("shortPercentOfFloat"),
                "days_to_cover":   info.get("shortRatio"),
                "shares_short":    info.get("sharesShort"),
            },
            "source":         "yfinance",
        }
    except Exception as e:
        log.warning(f"get_fundamentals({ticker}) failed: {e}")
        return {"source": "yfinance", "error": str(e),
                "short_interest": {"short_float_pct": None,
                                   "days_to_cover": None,
                                   "shares_short": None},
                **{k: None for k in ("pe_ratio","price_to_book","ev_ebitda",
                                     "price_to_sales","roe","debt_equity",
                                     "revenue_growth","gross_margin",
                                     "market_cap","sector","industry","name")}}
```

- [ ] **Step 4: Run tests to confirm they pass**

```
pytest tests/unit/test_yfinance_short_interest.py -v
```
Expected: 3 tests `PASSED`

- [ ] **Step 5: Run full test suite to check no regressions**

```
pytest tests/ -x -q
```
Expected: all tests pass (the existing `test_yfinance_client.py` integration tests mock `yf.Ticker` differently — check they still pass)

- [ ] **Step 6: Commit**

```
git add data/yfinance_client.py tests/unit/test_yfinance_short_interest.py
git commit -m "feat(d6): extract short interest fields from yfinance get_fundamentals"
```

---

## Task 2: D2 — Expand FRED macro snapshot with PCE and yield curve

**Files:**
- Modify: `data/fred_client.py`
- Modify: `tests/integration/test_fred_client.py`

- [ ] **Step 1: Write failing tests**

Add these two tests to `tests/integration/test_fred_client.py` (append after the existing tests):

```python
def test_get_macro_snapshot_includes_pce_and_yield_curve():
    import pandas as pd
    mock_fred = MagicMock()
    values = {
        "DFF": 5.33, "CPIAUCSL": 315.2, "GDP": 28000.0,
        "UNRATE": 3.9, "PCE": 21000.0, "GS10": 4.25, "GS2": 4.85,
    }
    mock_fred.get_series.side_effect = lambda sid: pd.Series([values[sid]])
    with patch("data.fred_client.Fred", return_value=mock_fred):
        result = FredClient(api_key="test").get_macro_snapshot()
    assert result["pce"] == 21000.0
    assert abs(result["yield_curve_spread"] - (4.25 - 4.85)) < 0.001


def test_get_macro_snapshot_yield_curve_none_when_series_fails():
    import pandas as pd
    mock_fred = MagicMock()
    def side_effect(sid):
        if sid in ("GS10", "GS2"):
            raise Exception("series unavailable")
        values = {"DFF": 5.33, "CPIAUCSL": 315.2, "GDP": 28000.0, "UNRATE": 3.9, "PCE": 21000.0}
        return pd.Series([values[sid]])
    mock_fred.get_series.side_effect = side_effect
    with patch("data.fred_client.Fred", return_value=mock_fred):
        result = FredClient(api_key="test").get_macro_snapshot()
    assert result["yield_curve_spread"] is None
    assert result["source"] == "fred"
```

- [ ] **Step 2: Run to confirm tests fail**

```
pytest tests/integration/test_fred_client.py -v
```
Expected: 2 new tests `FAILED` — `KeyError: 'pce'`

- [ ] **Step 3: Implement in `data/fred_client.py`**

Replace `get_macro_snapshot()` with:

```python
def get_macro_snapshot(self) -> dict:
    try:
        fred = Fred(api_key=self._api_key)
        errors: list = []

        def _latest(series_id: str) -> Optional[float]:
            try:
                s = fred.get_series(series_id)
                return float(s.iloc[-1])
            except Exception as e:
                errors.append(f"{series_id}: {e}")
                return None

        gs10 = _latest("GS10")
        gs2  = _latest("GS2")
        yield_curve = (gs10 - gs2) if gs10 is not None and gs2 is not None else None

        result = {
            "fed_funds_rate":     _latest("DFF"),
            "cpi":                _latest("CPIAUCSL"),
            "gdp":                _latest("GDP"),
            "unemployment":       _latest("UNRATE"),
            "pce":                _latest("PCE"),
            "yield_curve_spread": yield_curve,
            "source": "fred",
        }
        if errors:
            result["error"] = "; ".join(errors)
        log.info(f"FRED snapshot — rate:{result['fed_funds_rate']} "
                 f"cpi:{result['cpi']} pce:{result['pce']} "
                 f"yield_curve:{result['yield_curve_spread']}")
        return result
    except Exception as e:
        log.warning(f"FRED macro_snapshot failed: {e}")
        return {"fed_funds_rate": None, "cpi": None, "gdp": None,
                "unemployment": None, "pce": None, "yield_curve_spread": None,
                "source": "fred", "error": str(e)}
```

- [ ] **Step 4: Run tests to confirm they pass**

```
pytest tests/integration/test_fred_client.py -v
```
Expected: all 4 tests `PASSED`

- [ ] **Step 5: Run full suite for regressions**

```
pytest tests/ -x -q
```
Expected: all pass. Note: the aggregator test mocks `fred.get_macro_snapshot` so it won't be affected.

- [ ] **Step 6: Commit**

```
git add data/fred_client.py tests/integration/test_fred_client.py
git commit -m "feat(d2): add PCE and yield curve spread to FRED macro snapshot"
```

---

## Task 3: D3 — InsiderClient (OpenInsider CSV)

**Files:**
- Create: `data/insider_client.py`
- Create: `tests/unit/test_insider_client.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_insider_client.py`:

```python
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
```

- [ ] **Step 2: Run to confirm tests fail**

```
pytest tests/unit/test_insider_client.py -v
```
Expected: `ERROR` — `ModuleNotFoundError: No module named 'data.insider_client'`

- [ ] **Step 3: Create `data/insider_client.py`**

```python
import csv
import io
import requests
from logger import get_logger

log = get_logger("insider")

OPENINSIDER_URL = "https://openinsider.com/screener"


class InsiderClient:
    def get_transactions(self, ticker: str, days: int = 90) -> dict:
        try:
            params = {"s": ticker, "fd": days, "csv": 1}
            r = requests.get(OPENINSIDER_URL, params=params, timeout=15,
                             headers={"User-Agent": "HedgeFund Analyser"})
            if not r.ok:
                log.warning(f"InsiderClient({ticker}) HTTP {r.status_code}")
                return {"transactions": [], "source": "openinsider"}
            transactions = self._parse_csv(r.text)
            log.info(f"InsiderClient({ticker}): {len(transactions)} transactions")
            return {"transactions": transactions, "source": "openinsider"}
        except Exception as e:
            log.warning(f"InsiderClient({ticker}) failed: {e}")
            return {"transactions": [], "source": "openinsider", "error": str(e)}

    def _parse_csv(self, text: str) -> list:
        # OpenInsider CSV columns (0-indexed):
        # 0:X  1:Filing Date  2:Trade Date  3:Ticker  4:Insider Name
        # 5:Title  6:Trade Type  7:Price  8:Qty  9:Owned  10:ΔOwn  11:Value
        transactions = []
        reader = csv.reader(io.StringIO(text))
        next(reader, None)  # skip header row
        for row in reader:
            if len(row) < 12:
                continue
            try:
                trade_type_raw = row[6].strip().lower()
                transaction_type = "buy" if trade_type_raw.startswith("p") else "sell"
                price = float(row[7].replace("$", "").replace(",", "").strip() or 0)
                shares = int(row[8].replace(",", "").strip() or 0)
                value = float(row[11].replace("$", "").replace(",", "").strip() or 0)
                transactions.append({
                    "date":             row[1].strip(),
                    "officer_name":     row[4].strip(),
                    "title":            row[5].strip(),
                    "transaction_type": transaction_type,
                    "shares":           shares,
                    "price_per_share":  price,
                    "value":            value,
                })
            except (ValueError, IndexError):
                continue
        return transactions
```

- [ ] **Step 4: Run tests to confirm they pass**

```
pytest tests/unit/test_insider_client.py -v
```
Expected: 6 tests `PASSED`

- [ ] **Step 5: Run full suite for regressions**

```
pytest tests/ -x -q
```
Expected: all pass

- [ ] **Step 6: Commit**

```
git add data/insider_client.py tests/unit/test_insider_client.py
git commit -m "feat(d3): add InsiderClient using OpenInsider free CSV endpoint"
```

---

## Task 4: Wire D3 + D6 into the aggregator and orchestrator

**Files:**
- Modify: `data/aggregator.py`
- Modify: `pipeline/orchestrator.py`
- Modify: `tests/integration/test_aggregator.py`

- [ ] **Step 1: Update the aggregator test fixture first**

In `tests/integration/test_aggregator.py`, update the `mock_clients` fixture to add the `insider` mock, and update the `fred` mock to include the new fields. Replace the fixture body:

```python
@pytest.fixture
def mock_clients():
    yf = MagicMock()
    yf.get_price.return_value = {"price": 183.50, "source": "yfinance"}
    yf.get_fundamentals.return_value = {
        "pe_ratio": 28.5, "market_cap": 2_800_000_000_000,
        "sector": "Technology", "source": "yfinance",
        "short_interest": {"short_float_pct": 0.043,
                           "days_to_cover": 2.1,
                           "shares_short": 95_000_000},
    }
    yf.get_ohlcv.return_value = {"records": [{"Date": "2026-05-10", "Close": 183.5}], "source": "yfinance"}
    yf.get_sector_peers.return_value = ["MSFT", "GOOGL"]

    mm = MagicMock()
    mm.get_snapshot.return_value = {"price": 183.50, "source": "massive_market"}
    mm.get_news.return_value = {"articles": [{"title": "AAPL beats earnings"}],
                                "source": "massive_market", "rate_limited": False}
    mm.get_analyst_ratings.return_value = {"buy": 32, "hold": 8, "sell": 2, "source": "massive_market"}

    av = MagicMock()
    av.get_income_statement.return_value = {"annual": [{"totalRevenue": "391035000000"}],
                                             "quarterly": [], "source": "alpha_vantage", "rate_limited": False}
    av.get_balance_sheet.return_value = {"annual": [], "quarterly": [], "source": "alpha_vantage", "rate_limited": False}
    av.get_cash_flow.return_value = {"annual": [], "quarterly": [], "source": "alpha_vantage", "rate_limited": False}
    av.get_earnings.return_value = {"quarterly": [{"reportedEPS": "1.65", "estimatedEPS": "1.61"}],
                                     "annual": [], "source": "alpha_vantage", "rate_limited": False}

    fred = MagicMock()
    fred.get_macro_snapshot.return_value = {
        "fed_funds_rate": 5.33, "cpi": 315.2, "gdp": 28000.0,
        "unemployment": 3.9, "pce": 21000.0, "yield_curve_spread": -0.60,
        "source": "fred",
    }

    reddit = MagicMock()
    reddit.get_posts.return_value = {"posts": [], "total_posts": 0, "source": "reddit"}

    edgar = MagicMock()
    edgar.search_filings.return_value = {"filings": [], "source": "sec_edgar"}

    insider = MagicMock()
    insider.get_transactions.return_value = {
        "transactions": [
            {"date": "2026-05-01", "officer_name": "Cook Timothy D",
             "title": "CEO", "transaction_type": "buy",
             "shares": 5000, "price_per_share": 183.50, "value": 917500.0},
        ],
        "source": "openinsider",
    }

    cache = MagicMock()
    cache.get.return_value = None  # cache miss — always fetch fresh

    db = MagicMock()
    return {"yf": yf, "mm": mm, "av": av, "fred": fred,
            "reddit": reddit, "edgar": edgar, "insider": insider,
            "cache": cache, "db": db}
```

Also append these two new tests at the end of `tests/integration/test_aggregator.py`:

```python
def test_insider_transactions_in_bundle(mock_clients, tmp_path):
    agg = DataAggregator(**mock_clients, debug_dir=tmp_path)
    bundle = agg.fetch("AAPL", run_id=10)
    assert "insider_transactions" in bundle["data"]
    txns = bundle["data"]["insider_transactions"]["transactions"]
    assert len(txns) == 1
    assert txns[0]["transaction_type"] == "buy"
    assert bundle["manifest"]["insider_transactions"]["status"] == "ok"


def test_short_interest_in_manifest(mock_clients, tmp_path):
    agg = DataAggregator(**mock_clients, debug_dir=tmp_path)
    bundle = agg.fetch("AAPL", run_id=11)
    assert "short_interest" in bundle["manifest"]
    assert bundle["manifest"]["short_interest"]["status"] == "ok"
```

- [ ] **Step 2: Run tests to confirm they fail (DataAggregator missing `insider` param)**

```
pytest tests/integration/test_aggregator.py -v
```
Expected: `FAILED` — `TypeError: __init__() got an unexpected keyword argument 'insider'`

- [ ] **Step 3: Update `data/aggregator.py`**

Change the `__init__` signature (add `insider` after `edgar`):

```python
def __init__(self, yf, mm, av, fred, reddit, edgar, insider, cache, db,
             debug_dir: Path = DEBUG_BUNDLES_DIR):
    self._yf      = yf
    self._mm      = mm
    self._av      = av
    self._fred    = fred
    self._reddit  = reddit
    self._edgar   = edgar
    self._insider = insider
    self._cache   = cache
    self._db      = db
    self._debug_dir = debug_dir
    self._debug_dir.mkdir(parents=True, exist_ok=True)
```

Add a short interest manifest entry immediately after the fundamentals block (after the `mb.add("pe_ratio", ...)` line):

```python
short = fund.get("short_interest", {})
mb.add("short_interest", bool(short.get("short_float_pct")),
       source="yfinance",
       status="ok" if short.get("short_float_pct") else "partial")
```

Add the insider fetch block after the SEC filings block (after the `mb.add("sec_10k", ...)` line):

```python
# ── Insider transactions ──────────────────────────────────────────────
cached_insider = self._cache.get(ticker, "insider_transactions")
if cached_insider:
    insider = cached_insider["data"]
    log.info(f"[run_{run_id}] insider_transactions: served from cache")
else:
    insider = self._insider.get_transactions(ticker, days=90)
    if insider.get("transactions"):
        self._cache.put(ticker, "insider_transactions", insider,
                        CacheTier.FOREVER, source="openinsider")
data["insider_transactions"] = insider
txn_count = len(insider.get("transactions", []))
mb.add("insider_transactions", txn_count > 0,
       source="openinsider",
       status="ok" if txn_count > 0 else "partial")
log.info(f"[run_{run_id}] insider_transactions: {txn_count} transactions")
```

- [ ] **Step 4: Update `pipeline/orchestrator.py`**

Add the import (after `from data.sec_edgar import SecEdgarClient`):

```python
from data.insider_client import InsiderClient
```

Update the `DataAggregator` construction (around line 158):

```python
aggregator = DataAggregator(
    yf=YFinanceClient(),
    mm=MassiveMarketClient(),
    av=AlphaVantageClient(),
    fred=FredClient(),
    reddit=RedditClient(),
    edgar=SecEdgarClient(),
    insider=InsiderClient(),
    cache=CacheManager(db=db),
    db=db,
)
```

- [ ] **Step 5: Run tests to confirm they pass**

```
pytest tests/integration/test_aggregator.py -v
```
Expected: all tests `PASSED` (including the 2 new ones)

- [ ] **Step 6: Run full suite for regressions**

```
pytest tests/ -x -q
```
Expected: all pass

- [ ] **Step 7: Commit**

```
git add data/aggregator.py pipeline/orchestrator.py tests/integration/test_aggregator.py
git commit -m "feat(d3,d6): wire InsiderClient and short interest into aggregator and orchestrator"
```

---

## Task 5: Update agent prompts

**Files:**
- Modify: `prompts/roles/macro_analyst.md`
- Modify: `prompts/roles/fundamental_analyst.md`
- Modify: `prompts/roles/technical_analyst.md`

No tests for prompt files — changes take effect immediately on next run.

- [ ] **Step 1: Update `prompts/roles/macro_analyst.md`**

Add bullet to Responsibilities section (after "Identify sector rotation signals..."):
```
- Assess yield curve shape (10Y–2Y spread) and PCE inflation trend as leading indicators — inverted curve (spread < 0) signals recession risk; PCE rising signals margin pressure
```

Add two fields to `raw_output` schema (after `"unemployment"`):
```json
"pce": <float>,
"yield_curve_spread": <float>,
```

- [ ] **Step 2: Update `prompts/roles/fundamental_analyst.md`**

Add bullet to Responsibilities section (after "Score the company 1–10..."):
```
- Factor insider buy/sell patterns from the last 90 days into conviction — cluster buying is a strong bull signal; cluster selling over a rising stock warrants scrutiny
```

Add field to `raw_output` schema (after `"key_metrics_note"`):
```json
"insider_activity": {
    "net_bias": "<buying|selling|neutral>",
    "notable_transactions": ["<str>"]
}
```

Where:
- `net_bias` is `"buying"` if total buy value > total sell value over 90 days, `"selling"` if inverse, `"neutral"` if no transactions or values are balanced
- `notable_transactions` is a list of plain-English strings, e.g. `"CEO bought 5,000 shares at $183.50 on 2026-05-01"`

- [ ] **Step 3: Update `prompts/roles/technical_analyst.md`**

Add bullet to Responsibilities section (after "Suggest an entry zone..."):
```
- Assess short interest as a squeeze risk factor and contrarian signal — high days-to-cover on an uptrending stock is a squeeze setup
```

Add field to `raw_output` schema (after `"pattern_notes"`):
```json
"short_interest": {
    "short_float_pct": <float>,
    "days_to_cover": <float>,
    "squeeze_risk": "<high|medium|low>"
}
```

Where the agent derives `squeeze_risk` as:
- `"high"`: `days_to_cover > 5` AND price in uptrend
- `"medium"`: `days_to_cover > 3` OR `short_float_pct > 0.10`
- `"low"`: otherwise or data not available

- [ ] **Step 4: Commit**

```
git add prompts/roles/macro_analyst.md prompts/roles/fundamental_analyst.md prompts/roles/technical_analyst.md
git commit -m "feat(d2,d3,d6): update macro, fundamental, technical agent prompts with new data fields"
```

---

## Task 6: Integration smoke test for all three new data nodes

**Files:**
- Create: `tests/integration/test_new_data_nodes.py`

- [ ] **Step 1: Write integration tests**

Create `tests/integration/test_new_data_nodes.py`:

```python
"""Smoke tests verifying D2/D3/D6 data nodes appear correctly in the bundle."""
import pytest
from unittest.mock import MagicMock
from data.aggregator import DataAggregator


@pytest.fixture
def full_mock_clients(tmp_path):
    yf = MagicMock()
    yf.get_price.return_value = {"price": 183.50, "source": "yfinance"}
    yf.get_fundamentals.return_value = {
        "pe_ratio": 28.5, "sector": "Technology", "source": "yfinance",
        "short_interest": {"short_float_pct": 0.12, "days_to_cover": 6.2,
                           "shares_short": 200_000_000},
    }
    yf.get_ohlcv.return_value = {"records": [{"Date": "2026-05-10", "Close": 183.5}], "source": "yfinance"}
    yf.get_sector_peers.return_value = []

    mm = MagicMock()
    mm.get_snapshot.return_value = {"price": 183.50, "source": "massive_market"}
    mm.get_news.return_value = {"articles": [], "source": "massive_market", "rate_limited": False}
    mm.get_analyst_ratings.return_value = {"source": "massive_market"}

    av = MagicMock()
    av.get_income_statement.return_value = {"annual": [], "quarterly": [], "source": "alpha_vantage", "rate_limited": False}
    av.get_balance_sheet.return_value = {"annual": [], "quarterly": [], "source": "alpha_vantage", "rate_limited": False}
    av.get_cash_flow.return_value = {"annual": [], "quarterly": [], "source": "alpha_vantage", "rate_limited": False}
    av.get_earnings.return_value = {"quarterly": [], "annual": [], "source": "alpha_vantage", "rate_limited": False}

    fred = MagicMock()
    fred.get_macro_snapshot.return_value = {
        "fed_funds_rate": 5.33, "cpi": 315.2, "gdp": 28000.0,
        "unemployment": 3.9, "pce": 21000.0, "yield_curve_spread": -0.60,
        "source": "fred",
    }

    reddit = MagicMock()
    reddit.get_posts.return_value = {"posts": [], "total_posts": 0, "source": "reddit"}

    edgar = MagicMock()
    edgar.search_filings.return_value = {"filings": [], "source": "sec_edgar"}

    insider = MagicMock()
    insider.get_transactions.return_value = {
        "transactions": [
            {"date": "2026-05-01", "officer_name": "Cook Timothy D",
             "title": "CEO", "transaction_type": "buy",
             "shares": 5000, "price_per_share": 183.50, "value": 917500.0},
        ],
        "source": "openinsider",
    }

    cache = MagicMock()
    cache.get.return_value = None

    db = MagicMock()
    return DataAggregator(yf=yf, mm=mm, av=av, fred=fred, reddit=reddit,
                          edgar=edgar, insider=insider, cache=cache,
                          db=db, debug_dir=tmp_path)


def test_d2_macro_data_in_bundle(full_mock_clients):
    bundle = full_mock_clients.fetch("AAPL", run_id=200)
    macro = bundle["data"]["macro"]
    assert macro["pce"] == 21000.0
    assert macro["yield_curve_spread"] == -0.60


def test_d3_insider_transactions_in_bundle(full_mock_clients):
    bundle = full_mock_clients.fetch("AAPL", run_id=201)
    insider = bundle["data"]["insider_transactions"]
    assert insider["source"] == "openinsider"
    assert len(insider["transactions"]) == 1
    assert insider["transactions"][0]["officer_name"] == "Cook Timothy D"


def test_d6_short_interest_in_fundamentals(full_mock_clients):
    bundle = full_mock_clients.fetch("AAPL", run_id=202)
    si = bundle["data"]["fundamentals"]["short_interest"]
    assert si["short_float_pct"] == 0.12
    assert si["days_to_cover"] == 6.2


def test_all_three_nodes_in_manifest(full_mock_clients):
    bundle = full_mock_clients.fetch("AAPL", run_id=203)
    manifest = bundle["manifest"]
    assert manifest["short_interest"]["status"] == "ok"
    assert manifest["insider_transactions"]["status"] == "ok"
    assert "fed_funds_rate" in manifest  # macro uses existing key


def test_insider_partial_when_no_transactions(tmp_path):
    """Empty insider activity is partial, not missing — valid for many stocks."""
    yf = MagicMock()
    yf.get_price.return_value = {"price": 50.0, "source": "yfinance"}
    yf.get_fundamentals.return_value = {
        "pe_ratio": 15.0, "sector": "Energy", "source": "yfinance",
        "short_interest": {"short_float_pct": None, "days_to_cover": None, "shares_short": None},
    }
    yf.get_ohlcv.return_value = {"records": [], "source": "yfinance"}
    yf.get_sector_peers.return_value = []
    mm = MagicMock()
    mm.get_snapshot.return_value = {"price": 50.0, "source": "massive_market"}
    mm.get_news.return_value = {"articles": [], "source": "massive_market", "rate_limited": False}
    mm.get_analyst_ratings.return_value = {"source": "massive_market"}
    av = MagicMock()
    av.get_income_statement.return_value = {"annual": [], "quarterly": [], "source": "alpha_vantage", "rate_limited": False}
    av.get_balance_sheet.return_value = {"annual": [], "quarterly": [], "source": "alpha_vantage", "rate_limited": False}
    av.get_cash_flow.return_value = {"annual": [], "quarterly": [], "source": "alpha_vantage", "rate_limited": False}
    av.get_earnings.return_value = {"quarterly": [], "annual": [], "source": "alpha_vantage", "rate_limited": False}
    fred = MagicMock()
    fred.get_macro_snapshot.return_value = {"fed_funds_rate": 5.33, "cpi": 315.2, "gdp": 28000.0,
                                             "unemployment": 3.9, "pce": 21000.0,
                                             "yield_curve_spread": -0.60, "source": "fred"}
    reddit = MagicMock()
    reddit.get_posts.return_value = {"posts": [], "total_posts": 0, "source": "reddit"}
    edgar = MagicMock()
    edgar.search_filings.return_value = {"filings": [], "source": "sec_edgar"}
    insider = MagicMock()
    insider.get_transactions.return_value = {"transactions": [], "source": "openinsider"}
    cache = MagicMock()
    cache.get.return_value = None
    db = MagicMock()

    agg = DataAggregator(yf=yf, mm=mm, av=av, fred=fred, reddit=reddit,
                         edgar=edgar, insider=insider, cache=cache,
                         db=db, debug_dir=tmp_path)
    bundle = agg.fetch("XOM", run_id=204)
    assert bundle["manifest"]["insider_transactions"]["status"] == "partial"
```

- [ ] **Step 2: Run to confirm tests pass**

```
pytest tests/integration/test_new_data_nodes.py -v
```
Expected: 5 tests `PASSED`

- [ ] **Step 3: Run full suite one final time**

```
pytest tests/ -x -q
```
Expected: all tests pass

- [ ] **Step 4: Commit**

```
git add tests/integration/test_new_data_nodes.py
git commit -m "test(d2,d3,d6): add integration smoke tests for new data nodes"
```

---

## Self-Review

**Spec coverage:**
- D2 PCE field → Task 2 ✓
- D2 yield curve spread → Task 2 ✓
- D2 fed into Macro Analyst prompt → Task 5 Step 1 ✓
- D3 InsiderClient with 90-day window → Task 3 ✓
- D3 cached FOREVER → Task 4 Step 3 (aggregator) ✓
- D3 fed into Fundamental Analyst prompt → Task 5 Step 2 ✓
- D6 short_float_pct + days_to_cover + shares_short → Task 1 ✓
- D6 zero new API calls → Task 1 (no new client) ✓
- D6 fed into Technical Analyst prompt → Task 5 Step 3 ✓
- Aggregator constructor updated → Task 4 ✓
- Orchestrator updated → Task 4 Step 4 ✓
- Manifest entries for all three nodes → Task 4 Step 3 ✓
- insider_transactions partial (not missing) when empty → Task 6 test_insider_partial... ✓

**Placeholder scan:** No TBDs, TODOs, or "similar to Task N" references found.

**Type consistency:**
- `InsiderClient.get_transactions()` → returns `{"transactions": list, "source": str}` — consistent across Task 3 definition, Task 4 aggregator usage, Task 6 tests ✓
- `short_interest` dict keys: `short_float_pct`, `days_to_cover`, `shares_short` — consistent across Task 1 implementation, Task 4 fixture, Task 5 prompt schema, Task 6 tests ✓
- `DataAggregator.__init__` param order: `yf, mm, av, fred, reddit, edgar, insider, cache, db` — consistent across Task 4 implementation and all test fixtures ✓
- FRED return keys: `pce`, `yield_curve_spread` — consistent across Task 2 implementation, Task 4 fixture, Task 5 prompt schema, Task 6 tests ✓
