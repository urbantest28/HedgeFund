# Data & Inputs Expansion — D2, D3, D6

**Date:** 2026-05-15
**Backlog items:** D2 (P2), D3 (P2), D6 (P3)
**Approach:** Option A — minimal surface area, free APIs only

---

## Scope

Three new data signals added to the aggregator pipeline:

| Item | Signal | Source | Target Agent |
|------|--------|---------|--------------|
| D2 | PCE inflation + yield curve (10Y–2Y spread) | FRED (free) | Macro Analyst |
| D3 | Insider transactions — Form 4 buys/sells, 90-day window | OpenInsider CSV (free, no API key) | Fundamental Analyst |
| D6 | Short interest — short float %, days-to-cover | yfinance `.info` (already fetched) | Technical Analyst |

D4 (options flow) is deprioritised — basic put/call ratio provides weak signal for the stock types analysed; will be revisited when a paid unusual-activity feed is available.

---

## Data Layer

### D2 — FRED expansion (`data/fred_client.py`)

Extend `get_macro_snapshot()` with two additional `_latest()` calls:

- `PCE` → PCE inflation level (Fed's preferred inflation measure)
- `GS10` and `GS2` → yield curve spread computed as `GS10 - GS2` (positive = normal, negative = inverted)

Both pulled in the same try/except block as existing series. No new method, no new cache key — the expanded payload is stored under the existing `fed_funds_rate` cache entry with `CacheTier.TTL_1D`.

Return dict gains two fields:
```python
{
    "fed_funds_rate": float,
    "cpi": float,
    "gdp": float,
    "unemployment": float,
    "pce": float,           # NEW
    "yield_curve_spread": float,  # NEW — GS10 minus GS2
    "source": "fred",
}
```

### D3 — InsiderClient (`data/insider_client.py`)

New file. Single public method:

```python
def get_transactions(self, ticker: str, days: int = 90) -> dict
```

Fetches: `https://openinsider.com/screener?s={ticker}&fd={days}&csv=1`

Parses CSV response (using Python's `csv` module — no new dependencies). Returns:

```python
{
    "transactions": [
        {
            "date": "YYYY-MM-DD",
            "officer_name": str,
            "title": str,
            "transaction_type": "buy" | "sell",
            "shares": int,
            "price_per_share": float,
            "value": float,
        },
        ...
    ],
    "source": "openinsider",
}
```

Error handling: returns `{"transactions": [], "source": "openinsider", "error": str}` on any failure. Cached with `CacheTier.FOREVER` (Form 4 filings are immutable).

OpenInsider CSV column mapping (stable for years):
- Column 1: filing date
- Column 4: officer name
- Column 5: title
- Column 6: transaction type (`P - Purchase` / `S - Sale`)
- Column 8: shares
- Column 9: price
- Column 11: value

### D6 — Short interest extraction (`data/yfinance_client.py`)

`get_fundamentals()` already calls `ticker.info`. Extract three additional fields from the same dict:

```python
"short_interest": {
    "short_float_pct": info.get("shortPercentOfFloat"),   # e.g. 0.043 = 4.3%
    "days_to_cover":   info.get("shortRatio"),             # days-to-cover
    "shares_short":    info.get("sharesShort"),
}
```

Included in the existing fundamentals return dict. Zero new API calls.

---

## Aggregator (`data/aggregator.py`)

### Constructor change

```python
def __init__(self, yf, mm, av, fred, reddit, edgar, insider, cache, db, ...):
```

`insider` is the new `InsiderClient` instance.

### New fetch block (after SEC filings)

```python
# ── Insider transactions ──────────────────────────────────────────────
cached_insider = self._cache.get(ticker, "insider_transactions")
if cached_insider:
    insider = cached_insider["data"]
else:
    insider = self._insider.get_transactions(ticker, days=90)
    if insider.get("transactions"):
        self._cache.put(ticker, "insider_transactions", insider,
                        CacheTier.FOREVER, source="openinsider")
data["insider_transactions"] = insider
mb.add("insider_transactions", bool(insider.get("transactions")),
       source="openinsider",
       status="ok" if insider.get("transactions") else "partial")
```

Note: empty transactions is `partial` not `missing` — many stocks have zero insider activity in any 90-day window. Non-critical field.

### Short interest manifest entry

Added after fundamentals block:

```python
short = fund.get("short_interest", {})
mb.add("short_interest", bool(short.get("short_float_pct")),
       source="yfinance",
       status="ok" if short.get("short_float_pct") else "partial")
```

Non-critical field.

### `main.py`

Construct `InsiderClient` and pass to `DataAggregator`:

```python
from data.insider_client import InsiderClient
insider = InsiderClient()
aggregator = DataAggregator(yf=..., ..., insider=insider, ...)
```

---

## Agent Prompt Updates

### `prompts/roles/macro_analyst.md`

**Responsibilities** — add bullet:
> - Assess yield curve shape (10Y–2Y spread) and PCE inflation trend as leading indicators

**`raw_output` schema** — add two fields:
```json
"pce": <float>,
"yield_curve_spread": <float>
```

### `prompts/roles/fundamental_analyst.md`

**Responsibilities** — add bullet:
> - Factor insider buy/sell patterns into conviction — cluster buying over 90 days is a strong bull signal; cluster selling warrants scrutiny

**`raw_output` schema** — add nested object:
```json
"insider_activity": {
    "net_bias": "<buying|selling|neutral>",
    "notable_transactions": ["<str>"]
}
```

`net_bias` is `buying` if buy value > sell value over 90 days, `selling` if inverse, `neutral` if no activity or balanced.

### `prompts/roles/technical_analyst.md`

**Responsibilities** — add bullet:
> - Assess short interest as a squeeze risk factor and contrarian signal

**`raw_output` schema** — add nested object:
```json
"short_interest": {
    "short_float_pct": <float>,
    "days_to_cover": <float>,
    "squeeze_risk": "<high|medium|low>"
}
```

Agent derives `squeeze_risk` from data:
- `high`: `days_to_cover > 5` and upward price trend
- `medium`: `days_to_cover > 3` or `short_float_pct > 0.10`
- `low`: otherwise

---

## Caching Strategy

| Data | Cache key | TTL | Rationale |
|------|-----------|-----|-----------|
| Macro (expanded) | `fed_funds_rate` | 1 day | FRED updates daily |
| Insider transactions | `insider_transactions` | Forever | Form 4s don't change |
| Short interest | Inside `fundamentals` | 1 day | Already on TTL_1D |

---

## Error Handling

All three data sources follow the existing graceful-degradation pattern:
- On failure: return empty/null payload with `error` key
- Manifest marks field `partial` (not `missing`) — agents are instructed to note the gap and reduce confidence, not fail
- No new agent prompt is blocked by missing D2/D3/D6 data

---

## Files Changed

| File | Change |
|------|--------|
| `data/fred_client.py` | Add `pce` and `yield_curve_spread` to `get_macro_snapshot()` |
| `data/insider_client.py` | New file — `InsiderClient` |
| `data/yfinance_client.py` | Extract short interest fields in `get_fundamentals()` |
| `data/aggregator.py` | Add `insider` param, new insider fetch block, short interest manifest entry |
| `main.py` | Construct and inject `InsiderClient` |
| `prompts/roles/macro_analyst.md` | Add PCE/yield curve fields and responsibility |
| `prompts/roles/fundamental_analyst.md` | Add insider activity field and responsibility |
| `prompts/roles/technical_analyst.md` | Add short interest field and responsibility |

---

## Out of Scope

- D4 (options flow / put/call ratio) — deprioritised, revisit with paid unusual-activity feed
- D5 (earnings call transcripts)
- Any UI changes — new data surfaces in the existing HTML report automatically via the agent JSON output
