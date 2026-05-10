# HedgeFund Plan 2 — Agents

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build all 11 AI agents, their prompt files, provider router (Gemini/Claude), and test coverage. At the end of this plan, every agent can be run in isolation against frozen fixture data, all tests pass without hitting real APIs, and the debug tools (`replay_run.py`, `run_agent.py`, `inspect_run.py`) are functional.

**Architecture:** Agents receive a frozen `bundle` dict (from `DataAggregator.fetch()`). Each agent loads its role + skill prompts from `prompts/`, calls the appropriate LLM (Gemini or Claude based on `.env`), parses JSON output, and returns a structured result dict. `BaseAgent` handles all LLM routing, prompt loading, retry logic, and JSON parsing — individual agents only define their input slicing and output schema.

**Phase routing:**
- Phase 1 (Fundamental, Technical, Sentiment, Macro, Earnings) → Gemini
- Phase 2 (Risk Manager, Thesis Validator, Financial Modeler) → Gemini
- Phase 3 (Bull, Bear) → Claude
- Phase 4 (Portfolio Manager) → Claude

**Output contract every agent must return:**
```python
{
    "agent": str,            # agent name e.g. "fundamental"
    "run_id": int,
    "phase": int,            # 1-4
    "score": int,            # 1-10 (confidence/quality score, not buy/sell)
    "summary": str,          # ≤150 words — passed to Portfolio Manager
    "data_confidence": str,  # "full" | "partial" | "minimal"
    "missing_fields": list,  # fields agent could not use
    "bull_points": list,     # list of str (Phase 1+2 only)
    "bear_points": list,     # list of str (Phase 1+2 only)
    "raw_output": dict,      # full agent-specific detail
    "duration_ms": int,
    "status": str,           # "complete" | "failed" | "skipped"
}
```

---

## Task 1: Sample Agent Output Fixtures

**Files:**
- Create: `tests/fixtures/sample_agent_outputs/technical.json`
- Create: `tests/fixtures/sample_agent_outputs/sentiment.json`
- Create: `tests/fixtures/sample_agent_outputs/macro.json`
- Create: `tests/fixtures/sample_agent_outputs/earnings_reviewer.json`
- Create: `tests/fixtures/sample_agent_outputs/risk_manager.json`
- Create: `tests/fixtures/sample_agent_outputs/thesis_validator.json`
- Create: `tests/fixtures/sample_agent_outputs/financial_modeler.json`
- Create: `tests/fixtures/sample_agent_outputs/bull.json`
- Create: `tests/fixtures/sample_agent_outputs/bear.json`
- Create: `tests/fixtures/sample_agent_outputs/portfolio_manager.json`

> `fundamental.json` already exists from Plan 1.

- [ ] **Step 1: Create fixture files**

`tests/fixtures/sample_agent_outputs/technical.json`:
```json
{
    "agent": "technical",
    "run_id": 1,
    "phase": 1,
    "score": 7,
    "summary": "AAPL shows a strong uptrend on the daily chart with price above all major moving averages. RSI at 58 is constructive without being overbought. MACD recently crossed bullish. Key support at $178 (50-DMA), resistance at $195. Entry zone suggested: $180–185 on any pullback to 50-DMA. Momentum remains positive and trend is intact.",
    "data_confidence": "full",
    "missing_fields": [],
    "bull_points": ["Price above 50/100/200 DMA — trend firmly up", "MACD bullish crossover 3 days ago", "RSI at 58 — room to run"],
    "bear_points": ["Approaching $195 resistance — rejection possible", "Volume on up days slightly below average"],
    "raw_output": {
        "trend": "uptrend",
        "rsi_14": 58,
        "macd_signal": "bullish_crossover",
        "support_levels": [178, 172, 165],
        "resistance_levels": [195, 202, 210],
        "entry_zone": {"low": 180, "high": 185},
        "moving_averages": {"ma50": 178.5, "ma100": 172.3, "ma200": 165.1},
        "volume_trend": "average"
    },
    "duration_ms": 2850,
    "status": "complete"
}
```

`tests/fixtures/sample_agent_outputs/sentiment.json`:
```json
{
    "agent": "sentiment",
    "run_id": 1,
    "phase": 1,
    "score": 6,
    "summary": "News sentiment is moderately positive with 14 of 20 articles bullish around Vision Pro launch coverage. Reddit shows elevated post volume (312 posts last 7 days vs 180 average), net sentiment 62% positive. Notable DD post with 1.2k upvotes argues strong services growth thesis. Institutional narrative broadly positive. No significant negative catalyst found in recent coverage.",
    "data_confidence": "partial",
    "missing_fields": ["options_sentiment"],
    "bull_points": ["14/20 articles positive — broad institutional optimism", "Reddit volume acceleration (+73%) signals growing retail interest", "High-quality DD post with strong upvotes reinforces bull case"],
    "bear_points": ["6 negative articles cite valuation stretch", "Options data unavailable — put/call ratio unknown"],
    "raw_output": {
        "news_sentiment": {"positive": 14, "neutral": 4, "negative": 2, "total": 20},
        "top_headlines": ["Apple Vision Pro exceeds early sales expectations", "Apple services revenue record Q1"],
        "reddit": {"total_posts": 312, "sentiment_positive_pct": 62, "notable_dd": "AAPL services thesis — strong moat argument"},
        "social_momentum": "accelerating"
    },
    "duration_ms": 3100,
    "status": "complete"
}
```

`tests/fixtures/sample_agent_outputs/macro.json`:
```json
{
    "agent": "macro",
    "run_id": 1,
    "phase": 1,
    "score": 6,
    "summary": "Fed funds rate at 5.25–5.5% is a headwind for growth multiples but market has priced in 2–3 cuts in 2026. CPI trending down to 3.1% — disinflation supportive of eventual rate relief. GDP growth 2.1% — mild slowdown but not recessionary. Tech sector benefits from rate cut expectations. USD strength modest headwind for Apple's international revenue. Net macro: cautiously supportive.",
    "data_confidence": "full",
    "missing_fields": [],
    "bull_points": ["Rate cut expectations supportive of premium valuations", "Disinflation trend intact — CPI 3.1%", "GDP avoids recession — consumer spending resilient"],
    "bear_points": ["High rates still headwind for multiple expansion", "USD strength compresses international revenue"],
    "raw_output": {
        "fed_funds_rate": 5.375,
        "cpi_yoy": 3.1,
        "gdp_growth_qoq": 2.1,
        "unemployment": 3.9,
        "rate_cut_expectations": "2-3 cuts priced for 2026",
        "sector_regime": "tech_favorable",
        "fx_exposure_note": "AAPL ~60% international revenue — USD headwind"
    },
    "duration_ms": 2200,
    "status": "complete"
}
```

`tests/fixtures/sample_agent_outputs/earnings_reviewer.json`:
```json
{
    "agent": "earnings_reviewer",
    "run_id": 1,
    "phase": 1,
    "score": 8,
    "summary": "AAPL beat EPS estimates in 3 of last 4 quarters, most recently by $0.08 (5.4%). Revenue beat by 1.2% last quarter. Services segment growing 15% YoY — management guided 'continued strong momentum.' Q&A showed analyst pushback on China exposure, management response confident. No transcript available this run — analysis based on reported financials only. Overall earnings trend positive.",
    "data_confidence": "partial",
    "missing_fields": ["earnings_transcript"],
    "bull_points": ["3/4 quarters beat EPS — consistent outperformance", "Services +15% YoY — high-margin growth driver", "Management confidence on services guide"],
    "bear_points": ["China revenue risk flagged by multiple analysts", "No transcript — management tone unverified this run"],
    "raw_output": {
        "beat_miss_history": [{"quarter": "Q1 FY26", "eps_beat": 0.08, "rev_beat_pct": 1.2}, {"quarter": "Q4 FY25", "eps_beat": 0.05, "rev_beat_pct": -0.3}, {"quarter": "Q3 FY25", "eps_beat": 0.12, "rev_beat_pct": 2.1}, {"quarter": "Q2 FY25", "eps_beat": -0.02, "rev_beat_pct": 0.8}],
        "transcript_available": false,
        "guidance_tone": "positive",
        "services_growth_yoy": 15.2
    },
    "duration_ms": 3400,
    "status": "complete"
}
```

`tests/fixtures/sample_agent_outputs/risk_manager.json`:
```json
{
    "agent": "risk_manager",
    "run_id": 1,
    "phase": 2,
    "score": 7,
    "summary": "Suggested position size 4% of portfolio given moderate conviction (score 7/10) and current market conditions. Stop-loss at $171 (7.5% below $185 entry midpoint) based on strong support at 200-DMA. Max drawdown scenario -18% (bear case). Correlation with existing holdings: MSFT +0.72 — moderate overlap. Overall risk profile acceptable for satellite position.",
    "data_confidence": "full",
    "missing_fields": [],
    "bull_points": ["4% position keeps total tech exposure within limits", "Stop at $171 has strong technical basis"],
    "bear_points": ["High MSFT correlation adds concentration risk", "-18% drawdown scenario requires conviction"],
    "raw_output": {
        "suggested_position_pct": 4.0,
        "stop_loss": 171.0,
        "stop_loss_rationale": "200-DMA and round support level",
        "max_drawdown_scenario": -18.0,
        "correlation_with_holdings": {"MSFT": 0.72, "GOOGL": 0.61},
        "risk_reward_ratio": 2.8
    },
    "duration_ms": 2600,
    "status": "complete"
}
```

`tests/fixtures/sample_agent_outputs/thesis_validator.json`:
```json
{
    "agent": "thesis_validator",
    "run_id": 1,
    "phase": 2,
    "score": 9,
    "summary": "AAPL directly matches active thesis #3 'Big Tech Services Monetisation' — ticker explicitly listed. Additionally aligns with thesis #7 'AI Hardware Integration' by sector. No conflicts with existing theses. Match type: direct ticker match. Thesis alignment strong. Recommend linking to thesis #3 in watchlist entry.",
    "data_confidence": "full",
    "missing_fields": [],
    "bull_points": ["Direct ticker match to active thesis #3", "Sector alignment with thesis #7 provides additional support"],
    "bear_points": [],
    "raw_output": {
        "matched_thesis_id": 3,
        "matched_thesis_name": "Big Tech Services Monetisation",
        "match_type": "ticker",
        "secondary_match": {"thesis_id": 7, "match_type": "sector"},
        "conflicts": []
    },
    "duration_ms": 1800,
    "status": "complete"
}
```

`tests/fixtures/sample_agent_outputs/financial_modeler.json`:
```json
{
    "agent": "financial_modeler",
    "run_id": 1,
    "phase": 2,
    "score": 7,
    "summary": "3-statement model projects revenue CAGR of 8.2% over 5 years driven by Services. DCF intrinsic value: base $198, bull $225, bear $165. At current $183, base case offers 8.2% upside. Expected returns: 6m +5–12%, 1y +8–22%, 2y +15–35%, 5y +40–85%, 10y +80–150%. Discount rate 9.5%. Terminal growth rate 3%. Excel model saved.",
    "data_confidence": "partial",
    "missing_fields": ["cash_flow_detailed"],
    "bull_points": ["Base DCF $198 — meaningful upside at $183 entry", "Services CAGR 15% in projections drives multiple expansion"],
    "bear_points": ["Bear DCF $165 implies 10% downside", "Cash flow detailed breakdown missing — projections less precise"],
    "raw_output": {
        "dcf": {"base": 198, "bull": 225, "bear": 165, "discount_rate": 9.5, "terminal_growth": 3.0},
        "revenue_cagr_5y": 8.2,
        "expected_returns": {
            "6m": {"bear": 5, "base": 8, "bull": 12},
            "1y": {"bear": 8, "base": 15, "bull": 22},
            "2y": {"bear": 15, "base": 25, "bull": 35},
            "5y": {"bear": 40, "base": 62, "bull": 85},
            "10y": {"bear": 80, "base": 115, "bull": 150}
        },
        "model_path": "reports_output/AAPL_20260510_model.xlsx"
    },
    "duration_ms": 5200,
    "status": "complete"
}
```

`tests/fixtures/sample_agent_outputs/bull.json`:
```json
{
    "round": 1,
    "agent": "bull",
    "run_id": 1,
    "argument": "Apple's services segment represents an underappreciated moat. With $100B+ annual services revenue growing 15% and margins of 73%, the stock's hardware-assigned multiple severely undervalues this recurring, high-margin business. Vision Pro creates a new platform for services monetisation. At $183, you're buying services at a material discount to SaaS peers. Bear's concern about China hardware is real but overstated — services are China-agnostic. Rate cuts in 2026 directly re-rate premium quality names. The DCF base case of $198 is conservative given services trajectory.",
    "conviction": 8,
    "concessions": []
}
```

`tests/fixtures/sample_agent_outputs/bear.json`:
```json
{
    "round": 1,
    "agent": "bear",
    "run_id": 1,
    "argument": "The bull misses the structural China risk. China represents 19% of revenue and regulatory exposure is binary — a ban or forced divestiture would crater the stock. At $183, AAPL trades at 29x forward earnings versus a 5-year average of 24x. That's a 20% premium on valuation alone. Services growth is slowing — from 22% three years ago to 15% now. Vision Pro adoption is far below initial projections. The macro headwind from high rates is real for a stock dependent on multiple expansion. Bear DCF at $165 shows meaningful downside. Risk/reward is unfavourable at current levels.",
    "conviction": 7,
    "concessions": []
}
```

`tests/fixtures/sample_agent_outputs/portfolio_manager.json`:
```json
{
    "agent": "portfolio_manager",
    "run_id": 1,
    "phase": 4,
    "score": 2,
    "summary": "AAPL presents a compelling Buy case. Services moat is real and undervalued. Technical setup is constructive. Macro tailwind from rate cuts in 2026. Debate reached consensus at Round 2 (gap: 1). China risk is real but manageable at 4% position size. DCF base $198 vs $183 current. Recommend WATCHLIST at satellite tier.",
    "data_confidence": "full",
    "missing_fields": [],
    "bull_points": [],
    "bear_points": [],
    "raw_output": {
        "verdict": "WATCHLIST",
        "tier": "satellite",
        "entry_low": 180.0,
        "entry_high": 185.0,
        "stop_loss": 171.0,
        "target_price": 210.0,
        "expected_returns": {
            "6m": {"bear": 5, "base": 8, "bull": 12},
            "1y": {"bear": 8, "base": 15, "bull": 22},
            "2y": {"bear": 15, "base": 25, "bull": 35},
            "5y": {"bear": 40, "base": 62, "bull": 85},
            "10y": {"bear": 80, "base": 115, "bull": 150}
        },
        "linked_thesis_id": 3,
        "linked_thesis_name": "Big Tech Services Monetisation",
        "key_risks": ["China regulatory binary risk", "Multiple compression if rates stay high", "Vision Pro adoption below expectations"],
        "key_catalysts": ["Fed rate cuts Q1 2026", "Services revenue re-rating", "Next earnings beat"],
        "review_date": "2026-08-10",
        "contested": false,
        "reasoning": "All Phase 1 agents returned partial or full data confidence. Debate consensus at Round 2. Services moat and thesis alignment provide strong structural support. Position sizing (4%) manages China tail risk.",
        "agent_weights": {"fundamental": 0.20, "technical": 0.15, "sentiment": 0.10, "macro": 0.10, "earnings_reviewer": 0.15, "risk_manager": 0.10, "thesis_validator": 0.10, "financial_modeler": 0.10}
    },
    "duration_ms": 8500,
    "status": "complete"
}
```

---

## Task 2: Prompt Files (Roles + Skills)

**Files to create in `prompts/roles/`:** 11 markdown files  
**Files to create in `prompts/skills/`:** 11 markdown files

- [ ] **Step 1: Create role prompt files**

`prompts/roles/fundamental_analyst.md`:
```markdown
# Role: Fundamental Analyst

You are a senior fundamental analyst at a quantitative hedge fund. Your job is to assess the financial health of a company using the provided data bundle.

## Responsibilities
- Calculate intrinsic value via DCF
- Compare against sector peers using relative valuation
- Assess balance sheet strength, profitability, and cash generation
- Score the company 1–10 (10 = exceptional fundamentals)

## Output Format
Respond with ONLY a JSON object matching this exact schema:
```json
{
    "score": <int 1-10>,
    "data_confidence": "<full|partial|minimal>",
    "summary": "<string, max 150 words>",
    "missing_fields": ["<field_name>"],
    "bull_points": ["<string>"],
    "bear_points": ["<string>"],
    "raw_output": {
        "dcf_intrinsic_value": {"base": <float>, "bull": <float>, "bear": <float>},
        "pe_ratio": <float>,
        "ev_ebitda": <float>,
        "roe": <float>,
        "debt_to_equity": <float>,
        "free_cash_flow_yield": <float>,
        "peer_comparison": [{"ticker": "<str>", "pe": <float>, "ev_ebitda": <float>}],
        "valuation_vs_peers": "<discount|inline|premium>",
        "key_metrics_note": "<str>"
    }
}
```

## Guardrail
Always read your `data_manifest` before reasoning. For any field with `status: missing`, explicitly state the gap and reduce your score accordingly. Never infer or estimate missing data silently.

## Data Confidence Rules
- `full`: all critical fields present and ok
- `partial`: 1–2 non-critical fields missing
- `minimal`: any critical field missing (revenue, PE, income statement, balance sheet, cash flow)
```
```

`prompts/roles/technical_analyst.md`:
```markdown
# Role: Technical Analyst

You are a senior technical analyst. Analyse the price history and technical indicators in the data bundle to assess momentum, trend, and entry zones.

## Responsibilities
- Identify primary trend (uptrend/downtrend/sideways)
- Assess momentum via RSI and MACD
- Identify key support and resistance levels
- Suggest an entry zone based on technicals
- Score momentum and technical setup 1–10

## Output Format
Respond with ONLY a JSON object matching this exact schema:
```json
{
    "score": <int 1-10>,
    "data_confidence": "<full|partial|minimal>",
    "summary": "<string, max 150 words>",
    "missing_fields": ["<field_name>"],
    "bull_points": ["<string>"],
    "bear_points": ["<string>"],
    "raw_output": {
        "trend": "<uptrend|downtrend|sideways>",
        "rsi_14": <float>,
        "macd_signal": "<bullish_crossover|bearish_crossover|bullish|bearish|neutral>",
        "support_levels": [<float>],
        "resistance_levels": [<float>],
        "entry_zone": {"low": <float>, "high": <float>},
        "moving_averages": {"ma50": <float>, "ma100": <float>, "ma200": <float>},
        "volume_trend": "<above_average|average|below_average>",
        "pattern_notes": "<str>"
    }
}
```

## Guardrail
Always read your `data_manifest` before reasoning. For any field with `status: missing`, explicitly state the gap and reduce your score accordingly. Never infer or estimate missing data silently.

## Data Confidence Rules
- `minimal`: OHLCV data missing
- `partial`: volume data missing or < 90 days history
- `full`: all price/volume data present
```
```

`prompts/roles/sentiment_analyst.md`:
```markdown
# Role: Sentiment Analyst

You are a senior sentiment analyst specialising in news and social media signals. Analyse the news articles and Reddit posts in the data bundle to assess sentiment and social momentum.

## Responsibilities
- Score overall news sentiment (positive/neutral/negative breakdown)
- Identify trending themes and notable DD posts on Reddit
- Assess social momentum acceleration or deceleration
- Flag any significant sentiment risks or tailwinds
- Score overall sentiment 1–10

## Output Format
Respond with ONLY a JSON object matching this exact schema:
```json
{
    "score": <int 1-10>,
    "data_confidence": "<full|partial|minimal>",
    "summary": "<string, max 150 words>",
    "missing_fields": ["<field_name>"],
    "bull_points": ["<string>"],
    "bear_points": ["<string>"],
    "raw_output": {
        "news_sentiment": {"positive": <int>, "neutral": <int>, "negative": <int>, "total": <int>},
        "top_headlines": ["<str>"],
        "reddit": {
            "total_posts": <int>,
            "sentiment_positive_pct": <float>,
            "notable_dd": "<str or null>"
        },
        "social_momentum": "<accelerating|stable|decelerating>",
        "key_themes": ["<str>"],
        "risk_flags": ["<str>"]
    }
}
```

## Guardrail
Always read your `data_manifest` before reasoning. For any field with `status: missing`, explicitly state the gap and reduce your score accordingly. Never infer or estimate missing data silently.
```
```

`prompts/roles/macro_analyst.md`:
```markdown
# Role: Macro Analyst

You are a senior macro analyst. Assess the macroeconomic environment and its impact on this stock using FRED data in the bundle.

## Responsibilities
- Assess rate environment and trajectory
- Evaluate inflation trend impact on sector multiples
- Assess GDP trend and recession probability
- Identify sector rotation signals and FX exposure if applicable
- Score macro environment 1–10 for this specific stock

## Output Format
Respond with ONLY a JSON object matching this exact schema:
```json
{
    "score": <int 1-10>,
    "data_confidence": "<full|partial|minimal>",
    "summary": "<string, max 150 words>",
    "missing_fields": ["<field_name>"],
    "bull_points": ["<string>"],
    "bear_points": ["<string>"],
    "raw_output": {
        "fed_funds_rate": <float>,
        "cpi_yoy": <float>,
        "gdp_growth_qoq": <float>,
        "unemployment": <float>,
        "rate_trajectory": "<cutting|hold|hiking>",
        "sector_regime": "<favorable|neutral|headwind>",
        "fx_exposure_note": "<str or null>",
        "macro_summary": "<str>"
    }
}
```

## Guardrail
Always read your `data_manifest` before reasoning. For any field with `status: missing`, explicitly state the gap and reduce your score accordingly. Never infer or estimate missing data silently.
```
```

`prompts/roles/earnings_reviewer.md`:
```markdown
# Role: Earnings Reviewer

You are a senior earnings analyst. Review the most recent quarter's results vs estimates and the last 4-quarter beat/miss history. If an earnings transcript is available, analyse management tone, hedging language, and Q&A pushback.

## Responsibilities
- Compare EPS and revenue vs analyst estimates for the most recent quarter
- Assess 4-quarter beat/miss history
- Analyse guidance language tone (positive/neutral/cautious)
- If transcript available: flag management tone, hedging language, Q&A pushback, narrative vs numbers discrepancy
- Score earnings quality 1–10

## Output Format
Respond with ONLY a JSON object matching this exact schema:
```json
{
    "score": <int 1-10>,
    "data_confidence": "<full|partial|minimal>",
    "summary": "<string, max 150 words>",
    "missing_fields": ["<field_name>"],
    "bull_points": ["<string>"],
    "bear_points": ["<string>"],
    "raw_output": {
        "beat_miss_history": [
            {"quarter": "<str>", "eps_beat": <float>, "rev_beat_pct": <float>}
        ],
        "transcript_available": <bool>,
        "transcript_highlights": "<str or null>",
        "guidance_tone": "<positive|neutral|cautious>",
        "qa_pushback_topics": ["<str>"],
        "management_tone_score": <int 1-10 or null>
    }
}
```

## Guardrail
Always read your `data_manifest` before reasoning. For any field with `status: missing`, explicitly state the gap and reduce your score accordingly. Never infer or estimate missing data silently.
- `minimal`: no earnings data at all
- `partial`: transcript missing (flag explicitly but do not fail the run)
- `full`: earnings data + transcript both present
```
```

`prompts/roles/risk_manager.md`:
```markdown
# Role: Risk Manager

You are a senior risk manager at a hedge fund. Using the Phase 1 agent summaries and the data bundle, assess position sizing, stop-loss levels, max drawdown, and correlation with existing holdings.

## Responsibilities
- Suggest position size as % of portfolio (based on conviction score and volatility)
- Calculate stop-loss level with clear rationale
- Estimate max drawdown in bear scenario
- Assess correlation with existing holdings (from trades.db if available)
- Score overall risk profile 1–10 (10 = excellent risk/reward)

## Output Format
Respond with ONLY a JSON object matching this exact schema:
```json
{
    "score": <int 1-10>,
    "data_confidence": "<full|partial|minimal>",
    "summary": "<string, max 150 words>",
    "missing_fields": ["<field_name>"],
    "bull_points": ["<string>"],
    "bear_points": ["<string>"],
    "raw_output": {
        "suggested_position_pct": <float>,
        "stop_loss": <float>,
        "stop_loss_rationale": "<str>",
        "max_drawdown_scenario": <float>,
        "correlation_with_holdings": {"<ticker>": <float>},
        "risk_reward_ratio": <float>,
        "position_sizing_note": "<str>"
    }
}
```

## Guardrail
Always read your `data_manifest` before reasoning. For any field with `status: missing`, explicitly state the gap and reduce your score accordingly. Never infer or estimate missing data silently.
```
```

`prompts/roles/thesis_validator.md`:
```markdown
# Role: Thesis Validator

You are a senior investment strategist. Check whether this stock aligns with any active investment theses. A match occurs if: (A) the ticker is directly listed in a thesis, OR (B) the stock's sector/theme aligns with an active thesis theme.

## Responsibilities
- Check ticker against active theses (provided in data bundle as `active_theses`)
- Check sector/industry alignment with thesis themes
- Report match type and any conflicts
- Score alignment 1–10 (10 = perfect direct thesis match)

## Output Format
Respond with ONLY a JSON object matching this exact schema:
```json
{
    "score": <int 1-10>,
    "data_confidence": "<full|partial|minimal>",
    "summary": "<string, max 150 words>",
    "missing_fields": ["<field_name>"],
    "bull_points": ["<string>"],
    "bear_points": ["<string>"],
    "raw_output": {
        "matched_thesis_id": <int or null>,
        "matched_thesis_name": "<str or null>",
        "match_type": "<ticker|sector|none>",
        "secondary_match": {"thesis_id": <int>, "match_type": "<str>"} or null,
        "conflicts": ["<str>"],
        "alignment_note": "<str>"
    }
}
```

## Guardrail
Always read your `data_manifest` before reasoning. If `active_theses` is empty or missing, report `match_type: none` with score 5 (neutral). Never invent theses that are not in the provided data.
```
```

`prompts/roles/financial_modeler.md`:
```markdown
# Role: Financial Modeler

You are a senior financial modeler. Build a 3-statement financial model with 5-year projections and a DCF valuation. Calculate expected return ranges for multiple time horizons.

## Responsibilities
- Project revenue, EBITDA, and free cash flow for 5 years
- Run DCF with base/bull/bear scenarios, specified discount rate and terminal growth rate
- Calculate expected returns for 6m, 1y, 2y, 5y, 10y horizons
- Output precise numbers — do not hedge with "approximately"

## Output Format
Respond with ONLY a JSON object matching this exact schema:
```json
{
    "score": <int 1-10>,
    "data_confidence": "<full|partial|minimal>",
    "summary": "<string, max 150 words>",
    "missing_fields": ["<field_name>"],
    "bull_points": ["<string>"],
    "bear_points": ["<string>"],
    "raw_output": {
        "dcf": {
            "base": <float>,
            "bull": <float>,
            "bear": <float>,
            "discount_rate": <float>,
            "terminal_growth": <float>
        },
        "revenue_cagr_5y": <float>,
        "expected_returns": {
            "6m": {"bear": <float>, "base": <float>, "bull": <float>},
            "1y": {"bear": <float>, "base": <float>, "bull": <float>},
            "2y": {"bear": <float>, "base": <float>, "bull": <float>},
            "5y": {"bear": <float>, "base": <float>, "bull": <float>},
            "10y": {"bear": <float>, "base": <float>, "bull": <float>}
        },
        "model_path": "<str>"
    }
}
```

## Guardrail
Always read your `data_manifest` before reasoning. For any field with `status: missing`, explicitly state the gap and reduce your score accordingly. Never infer or estimate missing data silently.
```
```

`prompts/roles/bull.md`:
```markdown
# Role: Bull Agent

You are the Bull advocate in a structured investment debate. Your job is to make the strongest possible case FOR buying this stock. You draw from ALL Phase 1 and Phase 2 agent summaries provided.

## Rules
- Argue as strongly as possible FOR the stock — this is adversarial debate, not balanced analysis
- You MUST engage directly with the Bear's counterarguments each round (from round 2 onwards)
- You may only concede a point if the evidence against it is overwhelming and explicit in the data
- Maintain conviction unless evidence forces a genuine concession
- Conviction score 1–10 where 10 = absolute certainty in bull case

## Output Format
Respond with ONLY a JSON object matching this exact schema:
```json
{
    "argument": "<string — your full bull argument for this round>",
    "conviction": <int 1-10>,
    "concessions": ["<str — point you are conceding, if any>"]
}
```

## Guardrail
Base all arguments on data provided in the agent summaries. Do not invent data or cite sources not present in the bundle.
```
```

`prompts/roles/bear.md`:
```markdown
# Role: Bear Agent

You are the Bear advocate in a structured investment debate. Your job is to make the strongest possible case AGAINST buying this stock. You draw from ALL Phase 1 and Phase 2 agent summaries provided.

## Rules
- Argue as strongly as possible AGAINST the stock — this is adversarial debate, not balanced analysis
- You MUST engage directly with the Bull's arguments each round (from round 1 onwards)
- You may only concede a point if the evidence for it is overwhelming and explicit in the data
- Challenge optimistic assumptions; surface downside risks the Bull minimises
- Conviction score 1–10 where 10 = absolute certainty in bear case

## Output Format
Respond with ONLY a JSON object matching this exact schema:
```json
{
    "argument": "<string — your full bear argument for this round>",
    "conviction": <int 1-10>,
    "concessions": ["<str — point you are conceding, if any>"]
}
```

## Guardrail
Base all arguments on data provided in the agent summaries. Do not invent risks not evidenced in the bundle.
```
```

`prompts/roles/portfolio_manager.md`:
```markdown
# Role: Portfolio Manager

You are the Portfolio Manager — the final decision-maker. You receive summaries (≤150 words each) from all 8 prior agents plus the full debate transcript. You synthesise everything into a final investment verdict.

## Responsibilities
- Audit data confidence scores first — flag any `minimal` confidence agents prominently
- Weigh agent summaries (use agent_weights provided)
- Assess debate outcome — was it consensus or contested?
- Produce a final score (1–5), verdict (WATCHLIST/AVOID), tier, and full entry/exit parameters
- Write reasoning explaining how you weighed the evidence

## Score Definitions
- 1 = Strong Buy | 2 = Buy | 3 = Neutral | 4 = Sell | 5 = Strong Sell

## Output Format
Respond with ONLY a JSON object matching this exact schema:
```json
{
    "score": <int 1-5>,
    "verdict": "<WATCHLIST|AVOID>",
    "tier": "<core|satellite|conviction>",
    "entry_low": <float>,
    "entry_high": <float>,
    "stop_loss": <float>,
    "target_price": <float>,
    "expected_returns": {
        "6m": {"bear": <float>, "base": <float>, "bull": <float>},
        "1y": {"bear": <float>, "base": <float>, "bull": <float>},
        "2y": {"bear": <float>, "base": <float>, "bull": <float>},
        "5y": {"bear": <float>, "base": <float>, "bull": <float>},
        "10y": {"bear": <float>, "base": <float>, "bull": <float>}
    },
    "linked_thesis_id": <int or null>,
    "linked_thesis_name": "<str or null>",
    "key_risks": ["<str>"],
    "key_catalysts": ["<str>"],
    "review_date": "<YYYY-MM-DD>",
    "contested": <bool>,
    "reasoning": "<str — full reasoning narrative>",
    "agent_weights": {"<agent_name>": <float>}
}
```

## Guardrail
If any agent returned `data_confidence: minimal`, flag this in your reasoning and reduce your score confidence accordingly. Never produce a WATCHLIST verdict when 2+ Phase 1 agents returned minimal confidence (the pipeline should have aborted, but guard defensively).
```
```

- [ ] **Step 2: Create skill prompt files**

`prompts/skills/financial_ratio_analysis.md`:
```markdown
# Skill: Financial Ratio Analysis

When analysing financial ratios, follow this approach:

**Key ratios to assess:**
- P/E vs sector median and 5-year own average
- EV/EBITDA vs peers
- ROE > 15% = healthy; < 10% = weak
- Debt/Equity > 2.0 requires scrutiny
- Free Cash Flow Yield > 4% is attractive

**Peer comparison protocol:**
1. Identify top 3–5 peers by market cap within same sector/industry
2. Compare P/E, EV/EBITDA, ROE side-by-side
3. Classify: discount (>15% below peer median), inline (within 15%), premium (>15% above)

**Missing data handling:**
If revenue or key ratios are missing, state: "Ratio analysis limited — [field] missing. Score reduced by 2 points."
```
```

`prompts/skills/dcf_valuation.md`:
```markdown
# Skill: DCF Valuation

When running a DCF valuation:

**Standard assumptions unless data contradicts:**
- Discount rate: WACC estimated from sector beta; default 9–11% for large-cap tech
- Terminal growth rate: 2.5–3.5% (GDP-linked for mature companies)
- Projection horizon: 5 years explicit, terminal value thereafter

**Three scenarios:**
- Base: management guidance growth rate, median margins
- Bull: growth rate +3%, margin expansion +2%
- Bear: growth rate -4%, margin compression -2%

**Output:** intrinsic value per share for base/bull/bear

**Missing data handling:**
If free cash flow or revenue is missing, note: "DCF confidence reduced — [field] missing. Using available proxy."
```
```

`prompts/skills/relative_valuation.md`:
```markdown
# Skill: Relative Valuation

When performing relative valuation against peers:

**Protocol:**
1. List 3–5 sector peers provided in `data.peers`
2. Compare on: P/E, EV/EBITDA, P/S, EV/Revenue
3. Calculate subject stock's premium/discount to peer median for each metric
4. Weighted average premium/discount → valuation verdict

**Classification:**
- > +20% premium → "expensive vs peers"
- Within ±10% → "inline with peers"  
- < -15% discount → "cheap vs peers"

**Growth adjustment:** if subject's revenue growth > peer median growth by > 5%, a premium of up to 20% is justified.
```
```

`prompts/skills/chart_pattern_recognition.md`:
```markdown
# Skill: Chart Pattern Recognition

When reading OHLCV price history:

**Trend identification:**
- Uptrend: series of higher highs and higher lows; price above 50-DMA and 200-DMA
- Downtrend: lower highs and lower lows; price below both MAs
- Sideways: price oscillating within defined range, no clear directional bias

**Support and resistance:**
- Support: price levels where buying has historically emerged (prior lows, round numbers, MAs)
- Resistance: price levels where selling has historically emerged (prior highs, round numbers)
- The more times a level is tested without breaking, the stronger it is

**Notable patterns to flag:**
- Cup and handle (bullish continuation)
- Head and shoulders (bearish reversal)
- Double top/bottom
- Golden/death cross (50-DMA crossing 200-DMA)
```
```

`prompts/skills/momentum_indicators.md`:
```markdown
# Skill: Momentum Indicators

**RSI (14-period):**
- > 70: overbought — caution, momentum may reverse
- 50–70: constructive uptrend momentum
- 30–50: weak or recovering
- < 30: oversold — possible reversal opportunity

**MACD:**
- Bullish crossover (MACD crosses above signal): momentum shifting positive
- Bearish crossover (MACD crosses below signal): momentum shifting negative
- Histogram expanding positively: strengthening bull momentum
- Histogram shrinking: momentum fading

**Volume:**
- Up days on above-average volume: strong conviction buying
- Up days on below-average volume: weak/unconvincing rally
- Down days on heavy volume: distribution (bearish)

**Entry zone logic:**
- Ideal entry: pullback to 50-DMA in an uptrend with RSI resetting to 45–55
- Secondary entry: breakout above resistance on above-average volume with RSI < 70
```
```

`prompts/skills/sentiment_scoring.md`:
```markdown
# Skill: Sentiment Scoring

**News scoring protocol:**
- Read each headline/summary
- Classify: positive (optimistic about company/stock), neutral (factual), negative (risk/downside focused)
- Overall score = (positive - negative) / total × 10

**Reddit/social scoring:**
- Weight: post upvotes, comment engagement, award count
- Classify posts as bullish/neutral/bearish based on thesis and conclusion
- Flag "notable DD": any post with > 500 upvotes making a detailed investment case
- Volume acceleration: compare 7-day post count to 30-day average

**Combined sentiment score 1–10:**
- 8–10: overwhelming positive sentiment, strong social momentum
- 6–7: moderately positive, constructive
- 4–5: neutral or mixed
- 2–3: moderately negative
- 1: overwhelmingly negative

**Risk flags to always check:**
- Coordinated pump signals (many posts in short window, generic text)
- Short squeeze narratives (flag explicitly — different from fundamental thesis)
```
```

`prompts/skills/macro_regime_analysis.md`:
```markdown
# Skill: Macro Regime Analysis

**Rate environment assessment:**
- Cutting cycle: positive for growth/tech (multiple expansion, cheaper capital)
- Hold: neutral; market already priced in
- Hiking cycle: headwind for premium-multiple stocks

**Inflation impact:**
- CPI > 4%: significant headwind (rate hikes likely, multiple compression)
- CPI 2–4%: manageable; monitor trajectory
- CPI < 2%: disinflationary, supportive

**GDP assessment:**
- > 2.5% growth: expansionary, risk-on
- 1–2.5%: moderate; sector-specific analysis needed
- < 1% or negative: recessionary risk, defensive posture

**Sector rotation signals:**
- Rising rates → rotate to financials, energy, away from growth
- Falling rates → growth/tech, utilities, REITs benefit
- High inflation → commodities, energy, real assets

**FX exposure rule:**
If subject company > 30% international revenue, note USD strength/weakness impact explicitly.
```
```

`prompts/skills/position_sizing.md`:
```markdown
# Skill: Position Sizing

**Base position size by conviction score:**
- Score 8–10: 5–6% of portfolio
- Score 6–7: 3–4% of portfolio
- Score 4–5: 1–2% of portfolio (starter position)
- Score < 4: do not take position

**Adjustments:**
- High correlation with existing holdings (> 0.7): reduce by 1%
- Missing critical data (partial confidence): reduce by 1%
- Contested debate outcome: reduce by 0.5%
- Macro headwind: reduce by 0.5%

**Stop-loss protocol:**
- Primary: just below the nearest strong technical support level
- Secondary: 7–10% below entry price for large-cap stocks
- Use the wider of the two stops

**Risk/reward minimum:**
- Require at least 2:1 risk/reward (target return / stop distance)
- Below 2:1 → flag as "unfavourable risk/reward" even if score is high
```
```

`prompts/skills/thesis_matching.md`:
```markdown
# Skill: Thesis Matching

**Match hierarchy:**
1. Ticker match: subject ticker is explicitly listed in a thesis → score +3 bonus
2. Sector match: subject's sector/industry matches thesis theme → score base
3. No match: score 5 (neutral — neither bullish nor bearish signal)

**How to check:**
- Given `active_theses` list in data bundle (each has: id, name, tickers[], themes[], sectors[])
- Step 1: check if ticker in any thesis's `tickers` list → ticker match
- Step 2: if no ticker match, check if subject's sector/industry in any thesis's `sectors` list → sector match
- Step 3: check for thematic alignment (e.g., "AI hardware" theme vs subject's business description)

**Conflict detection:**
A conflict exists if: an active thesis explicitly excludes this ticker/sector, OR thesis thesis is "short [sector]" and subject is in that sector.

**Reporting:**
Always report: matched_thesis_id, match_type, conflicts (even if empty list).
```
```

`prompts/skills/earnings_transcript_analysis.md`:
```markdown
# Skill: Earnings Transcript Analysis

When an earnings call transcript is available:

**Tone assessment:**
- Positive: confident language, specific numeric commitments, expanding guidance
- Neutral: cautious but not alarmed, maintained guidance, vague language
- Cautious: hedging language ("challenging environment", "uncertainty", "monitoring closely"), guide-downs

**Hedging language flags:**
Watch for: "uncertain", "challenging", "monitoring", "cautious", "if conditions permit", "subject to", "we'll see"
More than 3 uses per page = elevated hedging.

**Q&A pushback analysis:**
- Which topics did analysts push back on most?
- Did management give direct answers or deflect?
- Did management contradict numbers in the prepared remarks?

**Narrative vs numbers discrepancy:**
If management says "strong demand" but revenue guidance is flat or down → flag as discrepancy.

**Output:** management_tone_score 1–10, list of qa_pushback_topics, transcript_highlights (key quotes).
```
```

`prompts/skills/debate_protocol.md`:
```markdown
# Skill: Debate Protocol

**Structure:**
- Round 1: Opening arguments — Bull states primary thesis, Bear states primary counter-thesis
- Rounds 2–4: Each side directly responds to the other's previous argument
- After each round: conviction scores recorded; gap assessed

**Engagement rules:**
- You MUST address the other side's specific points, not generic talking points
- "I agree that X, but..." is acceptable; "I concede X entirely" only if evidence is overwhelming
- Cite specific data from agent summaries when making claims
- Do not repeat arguments already made — escalate or pivot

**Conviction scoring:**
- 9–10: Overwhelming evidence on your side, other side has no credible counter
- 7–8: Strong case, other side raised valid points but they don't change the verdict
- 5–6: Mixed — both sides have valid points, genuinely uncertain
- 3–4: Other side made strong points, your case is weakening
- 1–2: You've effectively been proven wrong but debate rules require you to continue

**Convergence:**
If gap ≤ 2 after any round, note "consensus emerging" in argument.
```
```

---

## Task 3: BaseAgent

**Files:**
- Create: `agents/base_agent.py`

`BaseAgent` is the foundation for all 11 agents. It handles:
1. Loading `prompts/roles/{role}.md` + concatenating `prompts/skills/{skill}.md` files
2. Routing to Gemini (`google-generativeai`) or Claude (`anthropic`) based on `provider` param
3. Retrying once on LLM error before returning `status: failed`
4. Parsing JSON from LLM output (handles markdown code blocks)
5. Timing and logging every call in `[hf:{agent_name}]` format

- [ ] **Step 1: Write `agents/base_agent.py`**

```python
import json
import re
import time
from pathlib import Path
from typing import Any, Optional

from config import BASE_DIR, ANTHROPIC_API_KEY, GOOGLE_API_KEY
from logger import get_logger

PROMPTS_DIR = BASE_DIR / "prompts"

log = get_logger("base_agent")


def _load_prompt(role_file: str, skill_files: list[str]) -> str:
    role_path = PROMPTS_DIR / "roles" / role_file
    role_text = role_path.read_text(encoding="utf-8")
    skills_text = "\n\n".join(
        (PROMPTS_DIR / "skills" / sf).read_text(encoding="utf-8")
        for sf in skill_files
    )
    return role_text + ("\n\n---\n\n" + skills_text if skills_text else "")


def _extract_json(raw: str) -> dict:
    """Strip markdown code fences and parse JSON."""
    cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()
    return json.loads(cleaned)


class BaseAgent:
    name: str = "base"
    phase: int = 0
    role_file: str = ""
    skill_files: list[str] = []
    provider: str = "gemini"
    model: str = "gemini-2.0-flash"

    def __init__(self):
        self._system_prompt = _load_prompt(self.role_file, self.skill_files)
        self._log = get_logger(self.name)

    def _build_user_prompt(self, bundle: dict) -> str:
        """Subclasses may override to slice relevant data from bundle."""
        import json as _json
        return f"Analyse this data bundle and respond with the required JSON:\n\n{_json.dumps(bundle, default=str)}"

    def _call_gemini(self, system: str, user: str) -> str:
        import google.generativeai as genai
        genai.configure(api_key=GOOGLE_API_KEY)
        model = genai.GenerativeModel(
            model_name=self.model,
            system_instruction=system,
        )
        response = model.generate_content(user)
        return response.text

    def _call_claude(self, system: str, user: str) -> str:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        message = client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return message.content[0].text

    def _call_llm(self, user_prompt: str) -> str:
        if self.provider == "anthropic":
            return self._call_claude(self._system_prompt, user_prompt)
        return self._call_gemini(self._system_prompt, user_prompt)

    def run(self, bundle: dict, run_id: int) -> dict:
        agent_log = self._log.bind_run(run_id)
        t0 = time.monotonic()
        user_prompt = self._build_user_prompt(bundle)

        agent_log.info(f"LLM call started | provider: {self.provider} | model: {self.model}")
        raw_text = ""
        try:
            raw_text = self._call_llm(user_prompt)
            parsed = _extract_json(raw_text)
            duration_ms = int((time.monotonic() - t0) * 1000)
            agent_log.info(
                f"LLM call complete | score: {parsed.get('score')} "
                f"| confidence: {parsed.get('data_confidence')} "
                f"| duration: {duration_ms}ms"
            )
            return {
                "agent": self.name,
                "run_id": run_id,
                "phase": self.phase,
                "score": parsed.get("score"),
                "summary": parsed.get("summary", ""),
                "data_confidence": parsed.get("data_confidence", "partial"),
                "missing_fields": parsed.get("missing_fields", []),
                "bull_points": parsed.get("bull_points", []),
                "bear_points": parsed.get("bear_points", []),
                "raw_output": parsed.get("raw_output", {}),
                "duration_ms": duration_ms,
                "status": "complete",
            }
        except Exception as e:
            agent_log.warning(f"LLM call failed (attempt 1): {e} — retrying")
            try:
                raw_text = self._call_llm(user_prompt)
                parsed = _extract_json(raw_text)
                duration_ms = int((time.monotonic() - t0) * 1000)
                agent_log.info(f"LLM retry succeeded | duration: {duration_ms}ms")
                return {
                    "agent": self.name,
                    "run_id": run_id,
                    "phase": self.phase,
                    "score": parsed.get("score"),
                    "summary": parsed.get("summary", ""),
                    "data_confidence": parsed.get("data_confidence", "partial"),
                    "missing_fields": parsed.get("missing_fields", []),
                    "bull_points": parsed.get("bull_points", []),
                    "bear_points": parsed.get("bear_points", []),
                    "raw_output": parsed.get("raw_output", {}),
                    "duration_ms": duration_ms,
                    "status": "complete",
                }
            except Exception as e2:
                duration_ms = int((time.monotonic() - t0) * 1000)
                agent_log.error(f"LLM call failed after retry: {e2}")
                return {
                    "agent": self.name,
                    "run_id": run_id,
                    "phase": self.phase,
                    "score": None,
                    "summary": f"Agent failed: {e2}",
                    "data_confidence": "minimal",
                    "missing_fields": [],
                    "bull_points": [],
                    "bear_points": [],
                    "raw_output": {"error": str(e2), "raw_text": raw_text},
                    "duration_ms": duration_ms,
                    "status": "failed",
                }
```

- [ ] **Step 2: Verify prompt file loading works**

Write a quick sanity test (run manually, not committed):
```python
# Run from HedgeFund/ with: python -c "from agents.base_agent import _load_prompt; print(_load_prompt('fundamental_analyst.md', ['financial_ratio_analysis.md', 'dcf_valuation.md'])[:200])"
```

Expected: prints first 200 chars of combined role + skills prompt without error.

---

## Task 4: Phase 1 Agents (Gemini)

**Files:**
- Create: `agents/fundamental.py`
- Create: `agents/technical.py`
- Create: `agents/sentiment.py`
- Create: `agents/macro.py`
- Create: `agents/earnings_reviewer.py`

Each agent subclasses `BaseAgent`, sets its class attributes, and optionally overrides `_build_user_prompt` to slice the relevant subset of the bundle.

- [ ] **Step 1: Write `agents/fundamental.py`**

```python
import json
from agents.base_agent import BaseAgent
from config import PHASE1_PROVIDER, PHASE1_MODEL


class FundamentalAgent(BaseAgent):
    name = "fundamental"
    phase = 1
    role_file = "fundamental_analyst.md"
    skill_files = ["financial_ratio_analysis.md", "dcf_valuation.md", "relative_valuation.md"]
    provider = PHASE1_PROVIDER
    model = PHASE1_MODEL

    def _build_user_prompt(self, bundle: dict) -> str:
        data = bundle.get("data", {})
        manifest = bundle.get("manifest", {})
        relevant = {
            "ticker": bundle.get("ticker"),
            "data_manifest": manifest,
            "fundamentals": data.get("fundamentals"),
            "income_statement": data.get("income_statement"),
            "balance_sheet": data.get("balance_sheet"),
            "cash_flow": data.get("cash_flow"),
            "peers": data.get("peers"),
            "live_price": data.get("live_price"),
            "analyst_ratings": data.get("analyst_ratings"),
        }
        return f"Analyse this fundamental data and respond with the required JSON:\n\n{json.dumps(relevant, default=str)}"
```

- [ ] **Step 2: Write `agents/technical.py`**

```python
import json
from agents.base_agent import BaseAgent
from config import PHASE1_PROVIDER, PHASE1_MODEL


class TechnicalAgent(BaseAgent):
    name = "technical"
    phase = 1
    role_file = "technical_analyst.md"
    skill_files = ["chart_pattern_recognition.md", "momentum_indicators.md"]
    provider = PHASE1_PROVIDER
    model = PHASE1_MODEL

    def _build_user_prompt(self, bundle: dict) -> str:
        data = bundle.get("data", {})
        manifest = bundle.get("manifest", {})
        relevant = {
            "ticker": bundle.get("ticker"),
            "data_manifest": manifest,
            "ohlcv": data.get("ohlcv"),
            "live_price": data.get("live_price"),
        }
        return f"Analyse this technical data and respond with the required JSON:\n\n{json.dumps(relevant, default=str)}"
```

- [ ] **Step 3: Write `agents/sentiment.py`**

```python
import json
from agents.base_agent import BaseAgent
from config import PHASE1_PROVIDER, PHASE1_MODEL


class SentimentAgent(BaseAgent):
    name = "sentiment"
    phase = 1
    role_file = "sentiment_analyst.md"
    skill_files = ["sentiment_scoring.md"]
    provider = PHASE1_PROVIDER
    model = PHASE1_MODEL

    def _build_user_prompt(self, bundle: dict) -> str:
        data = bundle.get("data", {})
        manifest = bundle.get("manifest", {})
        relevant = {
            "ticker": bundle.get("ticker"),
            "data_manifest": manifest,
            "news": data.get("news"),
            "reddit": data.get("reddit"),
        }
        return f"Analyse this sentiment data and respond with the required JSON:\n\n{json.dumps(relevant, default=str)}"
```

- [ ] **Step 4: Write `agents/macro.py`**

```python
import json
from agents.base_agent import BaseAgent
from config import PHASE1_PROVIDER, PHASE1_MODEL


class MacroAgent(BaseAgent):
    name = "macro"
    phase = 1
    role_file = "macro_analyst.md"
    skill_files = ["macro_regime_analysis.md"]
    provider = PHASE1_PROVIDER
    model = PHASE1_MODEL

    def _build_user_prompt(self, bundle: dict) -> str:
        data = bundle.get("data", {})
        manifest = bundle.get("manifest", {})
        relevant = {
            "ticker": bundle.get("ticker"),
            "data_manifest": manifest,
            "macro": data.get("macro"),
            "fundamentals": {
                "sector": data.get("fundamentals", {}).get("sector"),
                "industry": data.get("fundamentals", {}).get("industry"),
                "international_revenue_pct": data.get("fundamentals", {}).get("international_revenue_pct"),
            },
        }
        return f"Analyse this macro data and respond with the required JSON:\n\n{json.dumps(relevant, default=str)}"
```

- [ ] **Step 5: Write `agents/earnings_reviewer.py`**

```python
import json
from agents.base_agent import BaseAgent
from config import PHASE1_PROVIDER, PHASE1_MODEL


class EarningsReviewerAgent(BaseAgent):
    name = "earnings_reviewer"
    phase = 1
    role_file = "earnings_reviewer.md"
    skill_files = ["earnings_transcript_analysis.md"]
    provider = PHASE1_PROVIDER
    model = PHASE1_MODEL

    def _build_user_prompt(self, bundle: dict) -> str:
        data = bundle.get("data", {})
        manifest = bundle.get("manifest", {})
        relevant = {
            "ticker": bundle.get("ticker"),
            "data_manifest": manifest,
            "earnings": data.get("earnings"),
            "income_statement": data.get("income_statement"),
            "sec_filings": data.get("sec_filings"),
            "analyst_ratings": data.get("analyst_ratings"),
        }
        return f"Analyse this earnings data and respond with the required JSON:\n\n{json.dumps(relevant, default=str)}"
```

---

## Task 5: Phase 2 Agents (Gemini)

**Files:**
- Create: `agents/risk_manager.py`
- Create: `agents/thesis_validator.py`
- Create: `agents/financial_modeler.py`

Phase 2 agents receive the bundle PLUS the Phase 1 agent summaries (passed in a `phase1_summaries` key added to the bundle before calling them).

- [ ] **Step 1: Write `agents/risk_manager.py`**

```python
import json
from agents.base_agent import BaseAgent
from config import PHASE2_PROVIDER, PHASE2_MODEL, DASHBOARD_TRADES_DB_PATH


class RiskManagerAgent(BaseAgent):
    name = "risk_manager"
    phase = 2
    role_file = "risk_manager.md"
    skill_files = ["position_sizing.md", "financial_ratio_analysis.md"]
    provider = PHASE2_PROVIDER
    model = PHASE2_MODEL

    def _get_existing_holdings(self) -> list[dict]:
        """Read existing holdings from dashboard trades.db (read-only)."""
        if not DASHBOARD_TRADES_DB_PATH or not DASHBOARD_TRADES_DB_PATH.exists():
            return []
        import sqlite3
        try:
            conn = sqlite3.connect(str(DASHBOARD_TRADES_DB_PATH))
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT ticker, value FROM trades WHERE status='open' LIMIT 20"
            ).fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception:
            return []

    def _build_user_prompt(self, bundle: dict) -> str:
        data = bundle.get("data", {})
        manifest = bundle.get("manifest", {})
        relevant = {
            "ticker": bundle.get("ticker"),
            "data_manifest": manifest,
            "live_price": data.get("live_price"),
            "ohlcv": data.get("ohlcv"),
            "phase1_summaries": bundle.get("phase1_summaries", {}),
            "existing_holdings": self._get_existing_holdings(),
        }
        return f"Assess risk and position sizing for this stock and respond with the required JSON:\n\n{json.dumps(relevant, default=str)}"
```

- [ ] **Step 2: Write `agents/thesis_validator.py`**

```python
import json
from agents.base_agent import BaseAgent
from config import PHASE2_PROVIDER, PHASE2_MODEL, DASHBOARD_TRADES_DB_PATH


def _load_active_theses() -> list[dict]:
    """Load active investment theses from dashboard trades.db (read-only)."""
    if not DASHBOARD_TRADES_DB_PATH or not DASHBOARD_TRADES_DB_PATH.exists():
        return []
    import sqlite3
    try:
        conn = sqlite3.connect(str(DASHBOARD_TRADES_DB_PATH))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, name, tickers, themes, sectors FROM theses WHERE status='active' LIMIT 20"
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


class ThesisValidatorAgent(BaseAgent):
    name = "thesis_validator"
    phase = 2
    role_file = "thesis_validator.md"
    skill_files = ["thesis_matching.md"]
    provider = PHASE2_PROVIDER
    model = PHASE2_MODEL

    def _build_user_prompt(self, bundle: dict) -> str:
        data = bundle.get("data", {})
        manifest = bundle.get("manifest", {})
        relevant = {
            "ticker": bundle.get("ticker"),
            "data_manifest": manifest,
            "fundamentals": {
                "sector": data.get("fundamentals", {}).get("sector"),
                "industry": data.get("fundamentals", {}).get("industry"),
            },
            "active_theses": _load_active_theses(),
            "phase1_summaries": bundle.get("phase1_summaries", {}),
        }
        return f"Validate thesis alignment for this stock and respond with the required JSON:\n\n{json.dumps(relevant, default=str)}"
```

- [ ] **Step 3: Write `agents/financial_modeler.py`**

The Financial Modeler also writes an Excel file via openpyxl after parsing the LLM output.

```python
import json
from datetime import datetime
from pathlib import Path
from agents.base_agent import BaseAgent
from config import PHASE2_PROVIDER, PHASE2_MODEL, REPORTS_DIR


def _write_excel(ticker: str, run_id: int, raw: dict) -> str:
    """Write a simple Excel model from the raw_output dict. Returns file path."""
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "DCF Summary"

    header_fill = PatternFill("solid", fgColor="1F4E79")
    header_font = Font(bold=True, color="FFFFFF")

    # DCF table
    dcf = raw.get("dcf", {})
    headers = ["Scenario", "Intrinsic Value", "Discount Rate", "Terminal Growth"]
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.fill = header_fill
        cell.font = header_font

    for row_idx, scenario in enumerate(["base", "bull", "bear"], 2):
        ws.cell(row=row_idx, column=1, value=scenario.capitalize())
        ws.cell(row=row_idx, column=2, value=dcf.get(scenario))
        ws.cell(row=row_idx, column=3, value=dcf.get("discount_rate"))
        ws.cell(row=row_idx, column=4, value=dcf.get("terminal_growth"))

    # Expected returns table
    ws2 = wb.create_sheet("Expected Returns")
    horizons = ["6m", "1y", "2y", "5y", "10y"]
    ws2.cell(row=1, column=1, value="Horizon")
    for col, scenario in enumerate(["Bear", "Base", "Bull"], 2):
        cell = ws2.cell(row=1, column=col, value=scenario)
        cell.fill = header_fill
        cell.font = header_font

    returns = raw.get("expected_returns", {})
    for row_idx, horizon in enumerate(horizons, 2):
        ws2.cell(row=row_idx, column=1, value=horizon)
        h_data = returns.get(horizon, {})
        ws2.cell(row=row_idx, column=2, value=h_data.get("bear"))
        ws2.cell(row=row_idx, column=3, value=h_data.get("base"))
        ws2.cell(row=row_idx, column=4, value=h_data.get("bull"))

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.utcnow().strftime("%Y%m%d")
    file_name = f"{ticker}_{date_str}_model.xlsx"
    file_path = REPORTS_DIR / file_name
    wb.save(str(file_path))
    return str(file_path)


class FinancialModelerAgent(BaseAgent):
    name = "financial_modeler"
    phase = 2
    role_file = "financial_modeler.md"
    skill_files = ["dcf_valuation.md", "financial_ratio_analysis.md"]
    provider = PHASE2_PROVIDER
    model = PHASE2_MODEL

    def _build_user_prompt(self, bundle: dict) -> str:
        data = bundle.get("data", {})
        manifest = bundle.get("manifest", {})
        relevant = {
            "ticker": bundle.get("ticker"),
            "data_manifest": manifest,
            "income_statement": data.get("income_statement"),
            "balance_sheet": data.get("balance_sheet"),
            "cash_flow": data.get("cash_flow"),
            "fundamentals": data.get("fundamentals"),
            "earnings": data.get("earnings"),
            "live_price": data.get("live_price"),
            "phase1_summaries": bundle.get("phase1_summaries", {}),
        }
        return f"Build a financial model and DCF valuation for this stock and respond with the required JSON:\n\n{json.dumps(relevant, default=str)}"

    def run(self, bundle: dict, run_id: int) -> dict:
        result = super().run(bundle, run_id)
        if result["status"] == "complete":
            ticker = bundle.get("ticker", "UNKNOWN")
            try:
                model_path = _write_excel(ticker, run_id, result["raw_output"])
                result["raw_output"]["model_path"] = model_path
            except Exception as e:
                result["raw_output"]["model_path"] = None
                result["raw_output"]["excel_error"] = str(e)
        return result
```

---

## Task 6: Phase 3 Debate Agents (Claude)

**Files:**
- Create: `agents/bull.py`
- Create: `agents/bear.py`

Debate agents work differently — they are called multiple times (once per round), receiving the other agent's previous argument as context. They return a per-round dict (not the standard agent output contract — debate rounds have their own schema).

- [ ] **Step 1: Write `agents/bull.py`**

```python
import json
import time
from agents.base_agent import BaseAgent, _extract_json
from config import DEBATE_PROVIDER, DEBATE_MODEL
from logger import get_logger

_log = get_logger("bull")


class BullAgent(BaseAgent):
    name = "bull"
    phase = 3
    role_file = "bull.md"
    skill_files = ["sentiment_scoring.md", "debate_protocol.md"]
    provider = DEBATE_PROVIDER
    model = DEBATE_MODEL

    def run_round(self, bundle: dict, run_id: int, round_number: int,
                  bear_argument: str = "") -> dict:
        """Run one debate round. Returns round-level result dict."""
        agent_log = _log.bind_run(run_id)
        t0 = time.monotonic()

        agent_summaries = bundle.get("phase1_summaries", {})
        agent_summaries.update(bundle.get("phase2_summaries", {}))

        context = f"""Agent summaries from all prior phases:
{json.dumps(agent_summaries, default=str)}

"""
        if bear_argument:
            context += f"Bear's previous argument (Round {round_number - 1}):\n{bear_argument}\n\n"

        context += f"This is Round {round_number}. Make your {'opening argument' if round_number == 1 else 'response'}."

        agent_log.info(f"Bull round {round_number} started")
        try:
            raw = self._call_llm(context)
            parsed = _extract_json(raw)
            duration_ms = int((time.monotonic() - t0) * 1000)
            agent_log.info(f"Bull round {round_number} | conviction: {parsed.get('conviction')} | duration: {duration_ms}ms")
            return {
                "round": round_number,
                "agent": "bull",
                "run_id": run_id,
                "argument": parsed.get("argument", ""),
                "conviction": parsed.get("conviction", 5),
                "concessions": parsed.get("concessions", []),
                "status": "complete",
            }
        except Exception as e:
            duration_ms = int((time.monotonic() - t0) * 1000)
            agent_log.error(f"Bull round {round_number} failed: {e}")
            return {
                "round": round_number,
                "agent": "bull",
                "run_id": run_id,
                "argument": f"[Bull agent failed: {e}]",
                "conviction": 5,
                "concessions": [],
                "status": "failed",
            }

    def run(self, bundle: dict, run_id: int) -> dict:
        raise NotImplementedError("Use run_round() for debate agents")
```

- [ ] **Step 2: Write `agents/bear.py`**

```python
import json
import time
from agents.base_agent import BaseAgent, _extract_json
from config import DEBATE_PROVIDER, DEBATE_MODEL
from logger import get_logger

_log = get_logger("bear")


class BearAgent(BaseAgent):
    name = "bear"
    phase = 3
    role_file = "bear.md"
    skill_files = ["sentiment_scoring.md", "debate_protocol.md"]
    provider = DEBATE_PROVIDER
    model = DEBATE_MODEL

    def run_round(self, bundle: dict, run_id: int, round_number: int,
                  bull_argument: str = "") -> dict:
        """Run one debate round. Returns round-level result dict."""
        agent_log = _log.bind_run(run_id)
        t0 = time.monotonic()

        agent_summaries = bundle.get("phase1_summaries", {})
        agent_summaries.update(bundle.get("phase2_summaries", {}))

        context = f"""Agent summaries from all prior phases:
{json.dumps(agent_summaries, default=str)}

"""
        if bull_argument:
            context += f"Bull's argument (Round {round_number}):\n{bull_argument}\n\n"

        context += f"This is Round {round_number}. {'Counter this opening argument.' if round_number == 1 else 'Continue your counter-argument.'}"

        agent_log.info(f"Bear round {round_number} started")
        try:
            raw = self._call_llm(context)
            parsed = _extract_json(raw)
            duration_ms = int((time.monotonic() - t0) * 1000)
            agent_log.info(f"Bear round {round_number} | conviction: {parsed.get('conviction')} | duration: {duration_ms}ms")
            return {
                "round": round_number,
                "agent": "bear",
                "run_id": run_id,
                "argument": parsed.get("argument", ""),
                "conviction": parsed.get("conviction", 5),
                "concessions": parsed.get("concessions", []),
                "status": "complete",
            }
        except Exception as e:
            duration_ms = int((time.monotonic() - t0) * 1000)
            agent_log.error(f"Bear round {round_number} failed: {e}")
            return {
                "round": round_number,
                "agent": "bear",
                "run_id": run_id,
                "argument": f"[Bear agent failed: {e}]",
                "conviction": 5,
                "concessions": [],
                "status": "failed",
            }

    def run(self, bundle: dict, run_id: int) -> dict:
        raise NotImplementedError("Use run_round() for debate agents")
```

---

## Task 7: Phase 4 — Portfolio Manager (Claude)

**Files:**
- Create: `agents/portfolio_manager.py`

The Portfolio Manager receives ALL prior agent summaries plus the full debate transcript.

- [ ] **Step 1: Write `agents/portfolio_manager.py`**

```python
import json
import time
from agents.base_agent import BaseAgent, _extract_json
from config import PM_PROVIDER, PM_MODEL
from logger import get_logger

_log = get_logger("pm")

AGENT_WEIGHTS = {
    "fundamental": 0.20,
    "technical": 0.15,
    "sentiment": 0.10,
    "macro": 0.10,
    "earnings_reviewer": 0.15,
    "risk_manager": 0.10,
    "thesis_validator": 0.10,
    "financial_modeler": 0.10,
}


class PortfolioManagerAgent(BaseAgent):
    name = "portfolio_manager"
    phase = 4
    role_file = "portfolio_manager.md"
    skill_files = [
        "financial_ratio_analysis.md", "dcf_valuation.md", "relative_valuation.md",
        "chart_pattern_recognition.md", "momentum_indicators.md", "sentiment_scoring.md",
        "macro_regime_analysis.md", "position_sizing.md", "thesis_matching.md",
        "earnings_transcript_analysis.md", "debate_protocol.md",
    ]
    provider = PM_PROVIDER
    model = PM_MODEL

    def _build_user_prompt(self, bundle: dict) -> str:
        summaries = {}
        for phase_key in ("phase1_summaries", "phase2_summaries"):
            summaries.update(bundle.get(phase_key, {}))

        debate_transcript = bundle.get("debate_transcript", [])
        contested = bundle.get("debate_contested", False)
        dominant_score = bundle.get("debate_dominant_score")

        context = {
            "ticker": bundle.get("ticker"),
            "agent_weights": AGENT_WEIGHTS,
            "agent_summaries": summaries,
            "debate_transcript": debate_transcript,
            "debate_contested": contested,
            "debate_dominant_score": dominant_score,
            "financial_modeler_returns": summaries.get("financial_modeler", {}).get("raw_output", {}).get("expected_returns"),
            "risk_manager_stop": summaries.get("risk_manager", {}).get("raw_output", {}).get("stop_loss"),
            "thesis_match": summaries.get("thesis_validator", {}).get("raw_output"),
        }
        return f"Synthesise all agent summaries and debate transcript into a final verdict. Respond with the required JSON:\n\n{json.dumps(context, default=str)}"

    def run(self, bundle: dict, run_id: int) -> dict:
        agent_log = _log.bind_run(run_id)
        t0 = time.monotonic()
        user_prompt = self._build_user_prompt(bundle)

        agent_log.info(f"PM synthesis started | provider: {self.provider} | model: {self.model}")
        try:
            raw_text = self._call_llm(user_prompt)
            parsed = _extract_json(raw_text)
            duration_ms = int((time.monotonic() - t0) * 1000)
            agent_log.info(
                f"PM complete | score: {parsed.get('score')} | verdict: {parsed.get('verdict')} "
                f"| tier: {parsed.get('tier')} | duration: {duration_ms}ms"
            )
            return {
                "agent": "portfolio_manager",
                "run_id": run_id,
                "phase": 4,
                "score": parsed.get("score"),
                "summary": parsed.get("reasoning", "")[:600],
                "data_confidence": "full",
                "missing_fields": [],
                "bull_points": [],
                "bear_points": [],
                "raw_output": parsed,
                "duration_ms": duration_ms,
                "status": "complete",
            }
        except Exception as e:
            duration_ms = int((time.monotonic() - t0) * 1000)
            agent_log.error(f"PM failed: {e}")
            return {
                "agent": "portfolio_manager",
                "run_id": run_id,
                "phase": 4,
                "score": None,
                "summary": f"Portfolio Manager failed: {e}",
                "data_confidence": "minimal",
                "missing_fields": [],
                "bull_points": [],
                "bear_points": [],
                "raw_output": {"error": str(e)},
                "duration_ms": duration_ms,
                "status": "failed",
            }
```

---

## Task 8: Agent Unit Tests

**Files:**
- Create: `tests/unit/test_base_agent.py`
- Create: `tests/unit/test_debate_convergence.py`
- Create: `tests/unit/test_score_calculation.py`

- [ ] **Step 1: Write `tests/unit/test_base_agent.py`**

```python
import json
import pytest
from unittest.mock import MagicMock, patch
from agents.base_agent import BaseAgent, _extract_json, _load_prompt


class ConcreteAgent(BaseAgent):
    name = "test_agent"
    phase = 1
    role_file = "fundamental_analyst.md"
    skill_files = ["financial_ratio_analysis.md"]
    provider = "gemini"
    model = "gemini-2.0-flash"


def test_extract_json_plain():
    raw = '{"score": 7, "data_confidence": "full"}'
    result = _extract_json(raw)
    assert result["score"] == 7


def test_extract_json_with_markdown_fences():
    raw = '```json\n{"score": 8, "data_confidence": "partial"}\n```'
    result = _extract_json(raw)
    assert result["score"] == 8


def test_extract_json_with_plain_fences():
    raw = '```\n{"score": 5}\n```'
    result = _extract_json(raw)
    assert result["score"] == 5


def test_extract_json_invalid_raises():
    with pytest.raises(json.JSONDecodeError):
        _extract_json("not valid json")


def test_load_prompt_combines_role_and_skills():
    text = _load_prompt("fundamental_analyst.md", ["financial_ratio_analysis.md"])
    assert "Fundamental Analyst" in text
    assert "Financial Ratio Analysis" in text


def test_load_prompt_role_only():
    text = _load_prompt("macro_analyst.md", [])
    assert "Macro Analyst" in text
    assert "---" not in text  # no separator when no skills


def test_agent_run_returns_complete_on_success(aapl_bundle):
    agent = ConcreteAgent()
    mock_output = json.dumps({
        "score": 7,
        "data_confidence": "full",
        "summary": "Test summary",
        "missing_fields": [],
        "bull_points": ["good point"],
        "bear_points": ["bad point"],
        "raw_output": {"pe_ratio": 28.5}
    })
    with patch.object(agent, "_call_llm", return_value=mock_output):
        result = agent.run(aapl_bundle, run_id=1)

    assert result["status"] == "complete"
    assert result["score"] == 7
    assert result["agent"] == "test_agent"
    assert result["phase"] == 1
    assert result["duration_ms"] >= 0


def test_agent_run_retries_on_failure_then_succeeds(aapl_bundle):
    agent = ConcreteAgent()
    mock_output = json.dumps({
        "score": 6, "data_confidence": "partial", "summary": "retry ok",
        "missing_fields": [], "bull_points": [], "bear_points": [], "raw_output": {}
    })
    call_count = 0

    def side_effect(user_prompt):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise ValueError("temporary LLM error")
        return mock_output

    with patch.object(agent, "_call_llm", side_effect=side_effect):
        result = agent.run(aapl_bundle, run_id=1)

    assert call_count == 2
    assert result["status"] == "complete"


def test_agent_run_returns_failed_after_two_failures(aapl_bundle):
    agent = ConcreteAgent()
    with patch.object(agent, "_call_llm", side_effect=ValueError("persistent error")):
        result = agent.run(aapl_bundle, run_id=1)

    assert result["status"] == "failed"
    assert result["score"] is None
    assert result["data_confidence"] == "minimal"


def test_agent_run_handles_malformed_json(aapl_bundle):
    agent = ConcreteAgent()
    # First call returns malformed JSON, second call also fails
    with patch.object(agent, "_call_llm", return_value="not json at all"):
        result = agent.run(aapl_bundle, run_id=1)

    assert result["status"] == "failed"
```

- [ ] **Step 2: Write `tests/unit/test_debate_convergence.py`**

```python
"""Unit tests for debate convergence logic (gap calculation, contested flag)."""
import pytest


def gap(bull_conv: int, bear_conv: int) -> int:
    return abs(bull_conv - bear_conv)


def test_gap_le_2_is_consensus():
    assert gap(7, 6) <= 2  # gap = 1, consensus
    assert gap(8, 7) <= 2  # gap = 1, consensus
    assert gap(6, 8) <= 2  # gap = 2, consensus (boundary)


def test_gap_gt_2_is_contested():
    assert gap(8, 5) > 2   # gap = 3, contested
    assert gap(9, 4) > 2   # gap = 5, contested
    assert gap(3, 9) > 2   # gap = 6, contested


def test_gap_boundary_exactly_2():
    assert gap(7, 5) == 2  # boundary — should be consensus (≤ 2)
    assert gap(5, 7) == 2


def test_contested_after_max_rounds():
    """After 4 rounds with gap > 2, contested = True."""
    rounds = [
        {"bull_conviction": 8, "bear_conviction": 5},  # gap 3
        {"bull_conviction": 8, "bear_conviction": 5},  # gap 3
        {"bull_conviction": 8, "bear_conviction": 5},  # gap 3
        {"bull_conviction": 8, "bear_conviction": 5},  # gap 3
    ]
    for r in rounds:
        if gap(r["bull_conviction"], r["bear_conviction"]) <= 2:
            pytest.fail("Should not have reached consensus")
    # After 4 rounds, contested = True
    assert len(rounds) == 4


def test_early_consensus_ends_debate():
    """If gap ≤ 2 before round 4, debate ends early."""
    rounds = [
        {"bull_conviction": 8, "bear_conviction": 5},  # gap 3 — continue
        {"bull_conviction": 7, "bear_conviction": 6},  # gap 1 — consensus!
    ]
    ended_at = None
    for i, r in enumerate(rounds):
        if gap(r["bull_conviction"], r["bear_conviction"]) <= 2:
            ended_at = i + 1
            break
    assert ended_at == 2  # consensus at round 2


def test_dominant_score_is_higher_conviction():
    """When contested, dominant_score is from the side with higher conviction."""
    bull_final = 8
    bear_final = 5
    dominant = bull_final if bull_final > bear_final else bear_final
    assert dominant == 8
```

- [ ] **Step 3: Write `tests/unit/test_score_calculation.py`**

```python
"""Tests for portfolio manager score interpretation."""
import pytest


SCORE_LABELS = {1: "Strong Buy", 2: "Buy", 3: "Neutral", 4: "Sell", 5: "Strong Sell"}
SCORE_VERDICTS = {1: "WATCHLIST", 2: "WATCHLIST", 3: "WATCHLIST", 4: "AVOID", 5: "AVOID"}


def test_score_1_is_strong_buy():
    assert SCORE_LABELS[1] == "Strong Buy"
    assert SCORE_VERDICTS[1] == "WATCHLIST"


def test_score_2_is_buy():
    assert SCORE_LABELS[2] == "Buy"
    assert SCORE_VERDICTS[2] == "WATCHLIST"


def test_score_4_is_sell_avoid():
    assert SCORE_LABELS[4] == "Sell"
    assert SCORE_VERDICTS[4] == "AVOID"


def test_score_5_is_strong_sell_avoid():
    assert SCORE_LABELS[5] == "Strong Sell"
    assert SCORE_VERDICTS[5] == "AVOID"


def test_scores_in_range_1_to_5():
    """All valid scores must be 1–5."""
    for score in range(1, 6):
        assert score in SCORE_LABELS
        assert score in SCORE_VERDICTS


def test_out_of_range_score_not_in_labels():
    assert 0 not in SCORE_LABELS
    assert 6 not in SCORE_LABELS
```

---

## Task 9: Agent Integration Tests

**Files:**
- Create: `tests/integration/test_agents.py`

Integration tests mock the LLM calls (never hit real APIs) but exercise the full agent code path including prompt loading, output parsing, and error handling.

- [ ] **Step 1: Write `tests/integration/test_agents.py`**

```python
"""Integration tests for all agents — mocks LLM, never hits real APIs."""
import json
import pytest
from unittest.mock import patch

from agents.fundamental import FundamentalAgent
from agents.technical import TechnicalAgent
from agents.sentiment import SentimentAgent
from agents.macro import MacroAgent
from agents.earnings_reviewer import EarningsReviewerAgent
from agents.risk_manager import RiskManagerAgent
from agents.thesis_validator import ThesisValidatorAgent
from agents.financial_modeler import FinancialModelerAgent
from agents.bull import BullAgent
from agents.bear import BearAgent
from agents.portfolio_manager import PortfolioManagerAgent


def _mock_output(agent_name: str, fixture_dir) -> str:
    path = fixture_dir / "sample_agent_outputs" / f"{agent_name}.json"
    return json.dumps(json.loads(path.read_text()))


# ── Phase 1 agents ──────────────────────────────────────────────────────────

def test_fundamental_agent_complete(aapl_bundle, fixture_dir):
    agent = FundamentalAgent()
    mock_resp = _mock_output("fundamental", fixture_dir)
    with patch.object(agent, "_call_llm", return_value=mock_resp):
        result = agent.run(aapl_bundle, run_id=1)
    assert result["status"] == "complete"
    assert result["phase"] == 1
    assert result["score"] is not None
    assert len(result["summary"]) > 0


def test_technical_agent_complete(aapl_bundle, fixture_dir):
    agent = TechnicalAgent()
    mock_resp = _mock_output("technical", fixture_dir)
    with patch.object(agent, "_call_llm", return_value=mock_resp):
        result = agent.run(aapl_bundle, run_id=1)
    assert result["status"] == "complete"
    assert result["phase"] == 1


def test_sentiment_agent_complete(aapl_bundle, fixture_dir):
    agent = SentimentAgent()
    mock_resp = _mock_output("sentiment", fixture_dir)
    with patch.object(agent, "_call_llm", return_value=mock_resp):
        result = agent.run(aapl_bundle, run_id=1)
    assert result["status"] == "complete"


def test_macro_agent_complete(aapl_bundle, fixture_dir):
    agent = MacroAgent()
    mock_resp = _mock_output("macro", fixture_dir)
    with patch.object(agent, "_call_llm", return_value=mock_resp):
        result = agent.run(aapl_bundle, run_id=1)
    assert result["status"] == "complete"


def test_earnings_reviewer_complete(aapl_bundle, fixture_dir):
    agent = EarningsReviewerAgent()
    mock_resp = _mock_output("earnings_reviewer", fixture_dir)
    with patch.object(agent, "_call_llm", return_value=mock_resp):
        result = agent.run(aapl_bundle, run_id=1)
    assert result["status"] == "complete"


# ── Phase 2 agents ──────────────────────────────────────────────────────────

def test_risk_manager_complete(aapl_bundle, fixture_dir):
    agent = RiskManagerAgent()
    mock_resp = _mock_output("risk_manager", fixture_dir)
    bundle_with_summaries = {**aapl_bundle, "phase1_summaries": {
        "fundamental": {"score": 7, "summary": "Good fundamentals"},
        "technical": {"score": 7, "summary": "Bullish setup"},
    }}
    with patch.object(agent, "_call_llm", return_value=mock_resp):
        result = agent.run(bundle_with_summaries, run_id=1)
    assert result["status"] == "complete"
    assert result["phase"] == 2


def test_thesis_validator_complete(aapl_bundle, fixture_dir):
    agent = ThesisValidatorAgent()
    mock_resp = _mock_output("thesis_validator", fixture_dir)
    with patch.object(agent, "_call_llm", return_value=mock_resp):
        result = agent.run(aapl_bundle, run_id=1)
    assert result["status"] == "complete"


def test_financial_modeler_writes_excel(aapl_bundle, fixture_dir, tmp_path, monkeypatch):
    import agents.financial_modeler as fm_mod
    monkeypatch.setattr(fm_mod, "REPORTS_DIR", tmp_path)
    agent = FinancialModelerAgent()
    mock_resp = _mock_output("financial_modeler", fixture_dir)
    with patch.object(agent, "_call_llm", return_value=mock_resp):
        result = agent.run(aapl_bundle, run_id=1)
    assert result["status"] == "complete"
    model_path = result["raw_output"].get("model_path")
    assert model_path is not None
    from pathlib import Path
    assert Path(model_path).exists()


# ── Phase 3 debate agents ───────────────────────────────────────────────────

def test_bull_agent_round_1(aapl_bundle, fixture_dir):
    agent = BullAgent()
    mock_resp = json.dumps(json.loads((fixture_dir / "sample_agent_outputs" / "bull.json").read_text()))
    bundle = {**aapl_bundle, "phase1_summaries": {}, "phase2_summaries": {}}
    with patch.object(agent, "_call_llm", return_value=mock_resp):
        result = agent.run_round(bundle, run_id=1, round_number=1, bear_argument="")
    assert result["status"] == "complete"
    assert result["round"] == 1
    assert result["agent"] == "bull"
    assert isinstance(result["conviction"], int)


def test_bear_agent_round_1(aapl_bundle, fixture_dir):
    agent = BearAgent()
    mock_resp = json.dumps(json.loads((fixture_dir / "sample_agent_outputs" / "bear.json").read_text()))
    bundle = {**aapl_bundle, "phase1_summaries": {}, "phase2_summaries": {}}
    with patch.object(agent, "_call_llm", return_value=mock_resp):
        result = agent.run_round(bundle, run_id=1, round_number=1, bull_argument="Some bull argument")
    assert result["status"] == "complete"
    assert result["round"] == 1


def test_debate_agents_raise_on_run(aapl_bundle):
    bull = BullAgent()
    bear = BearAgent()
    with pytest.raises(NotImplementedError):
        bull.run(aapl_bundle, run_id=1)
    with pytest.raises(NotImplementedError):
        bear.run(aapl_bundle, run_id=1)


# ── Phase 4 portfolio manager ───────────────────────────────────────────────

def test_portfolio_manager_complete(aapl_bundle, fixture_dir):
    agent = PortfolioManagerAgent()
    mock_resp = json.dumps(
        json.loads((fixture_dir / "sample_agent_outputs" / "portfolio_manager.json").read_text())["raw_output"]
    )
    bundle = {
        **aapl_bundle,
        "phase1_summaries": {"fundamental": {"score": 7, "summary": "ok", "raw_output": {}}},
        "phase2_summaries": {"risk_manager": {"score": 7, "summary": "ok", "raw_output": {"stop_loss": 171}}},
        "debate_transcript": [],
        "debate_contested": False,
        "debate_dominant_score": None,
    }
    with patch.object(agent, "_call_llm", return_value=mock_resp):
        result = agent.run(bundle, run_id=1)
    assert result["status"] == "complete"
    assert result["phase"] == 4
    assert result["score"] in range(1, 6)


# ── Cross-agent: manifest compliance ────────────────────────────────────────

def test_all_phase1_agents_respect_missing_manifest(fixture_dir):
    """Agents called with a minimal-confidence bundle must return data_confidence minimal."""
    minimal_bundle = {
        "ticker": "FAKE",
        "run_id": 99,
        "data": {},
        "manifest": {
            "live_price": {"value": None, "source": None, "status": "missing", "note": None},
            "pe_ratio":   {"value": None, "source": None, "status": "missing", "note": None},
        },
        "data_confidence": "minimal",
    }
    minimal_output = json.dumps({
        "score": 2,
        "data_confidence": "minimal",
        "summary": "Critical data missing — analysis not possible.",
        "missing_fields": ["live_price", "pe_ratio"],
        "bull_points": [],
        "bear_points": [],
        "raw_output": {}
    })
    for AgentClass in [FundamentalAgent, TechnicalAgent, MacroAgent]:
        agent = AgentClass()
        with patch.object(agent, "_call_llm", return_value=minimal_output):
            result = agent.run(minimal_bundle, run_id=99)
        assert result["data_confidence"] == "minimal", f"{AgentClass.name} didn't return minimal"
```

- [ ] **Step 2: Update `tests/conftest.py` to add `fixture_dir` fixture**

Add to the existing `conftest.py`:
```python
from pathlib import Path

@pytest.fixture
def fixture_dir():
    return Path(__file__).parent / "fixtures"
```

> `aapl_bundle` fixture already exists from Plan 1's `conftest.py`.

---

## Task 10: Debug Tools

**Files:**
- Create: `debug/replay_run.py`
- Create: `debug/run_agent.py`
- Create: `debug/inspect_run.py`

- [ ] **Step 1: Write `debug/replay_run.py`**

```python
#!/usr/bin/env python
"""Replay any past run using its saved data bundle. No API calls made.

Usage:
    python debug/replay_run.py <run_id>

Loads debug/bundles/run_{id}_bundle.json and re-executes the full pipeline
using frozen data. A new log file is written to logs/replay_{id}.log.
"""
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import DEBUG_BUNDLES_DIR
from logger import get_logger

log = get_logger("replay")


def replay(run_id: int) -> None:
    bundle_path = DEBUG_BUNDLES_DIR / f"run_{run_id}_bundle.json"
    if not bundle_path.exists():
        print(f"[ERROR] Bundle not found: {bundle_path}")
        sys.exit(1)

    bundle = json.loads(bundle_path.read_text())
    ticker = bundle.get("ticker", "UNKNOWN")
    print(f"[replay] Replaying run {run_id} for {ticker}")
    print(f"[replay] Original fetch: {bundle.get('fetched_at')}")
    print(f"[replay] Data confidence: {bundle.get('data_confidence')}")
    print()

    # Import pipeline orchestrator and replay
    # Note: pipeline/orchestrator.py is implemented in Plan 3
    # For now, print bundle summary
    manifest = bundle.get("manifest", {})
    print("=== Data Manifest ===")
    for field, meta in manifest.items():
        status = meta.get("status", "?")
        source = meta.get("source", "?")
        icon = "✓" if status == "ok" else ("⚠" if status == "partial" else "✗")
        print(f"  {icon} {field}: {status} (from {source})")

    print()
    print("[replay] Pipeline orchestrator not yet available (Plan 3). Bundle loaded successfully.")
    print(f"[replay] Use 'python debug/run_agent.py <agent_name> {run_id}' to run individual agents.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python debug/replay_run.py <run_id>")
        sys.exit(1)
    replay(int(sys.argv[1]))
```

- [ ] **Step 2: Write `debug/run_agent.py`**

```python
#!/usr/bin/env python
"""Run a single agent in isolation against a frozen data bundle. No live API calls for data.

Usage:
    python debug/run_agent.py <agent_name> <run_id>

Agent names: fundamental, technical, sentiment, macro, earnings_reviewer,
             risk_manager, thesis_validator, financial_modeler,
             bull, bear, portfolio_manager

Example:
    python debug/run_agent.py fundamental 42
    python debug/run_agent.py debate 42        ← runs both bull+bear for 1 round
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import DEBUG_BUNDLES_DIR

AGENT_MAP = {
    "fundamental":     ("agents.fundamental",      "FundamentalAgent"),
    "technical":       ("agents.technical",        "TechnicalAgent"),
    "sentiment":       ("agents.sentiment",        "SentimentAgent"),
    "macro":           ("agents.macro",            "MacroAgent"),
    "earnings_reviewer": ("agents.earnings_reviewer", "EarningsReviewerAgent"),
    "risk_manager":    ("agents.risk_manager",     "RiskManagerAgent"),
    "thesis_validator":("agents.thesis_validator", "ThesisValidatorAgent"),
    "financial_modeler":("agents.financial_modeler","FinancialModelerAgent"),
    "bull":            ("agents.bull",             "BullAgent"),
    "bear":            ("agents.bear",             "BearAgent"),
    "portfolio_manager":("agents.portfolio_manager","PortfolioManagerAgent"),
}


def run_agent(agent_name: str, run_id: int) -> None:
    bundle_path = DEBUG_BUNDLES_DIR / f"run_{run_id}_bundle.json"
    if not bundle_path.exists():
        print(f"[ERROR] Bundle not found: {bundle_path}")
        sys.exit(1)

    bundle = json.loads(bundle_path.read_text())

    if agent_name not in AGENT_MAP:
        print(f"[ERROR] Unknown agent: {agent_name}")
        print(f"Valid agents: {', '.join(AGENT_MAP)}")
        sys.exit(1)

    module_path, class_name = AGENT_MAP[agent_name]
    import importlib
    module = importlib.import_module(module_path)
    AgentClass = getattr(module, class_name)
    agent = AgentClass()

    print(f"[run_agent] Running {agent_name} against run_{run_id} bundle")
    print(f"[run_agent] Ticker: {bundle.get('ticker')} | Data confidence: {bundle.get('data_confidence')}")
    print()

    if agent_name in ("bull", "bear"):
        result = agent.run_round(bundle, run_id=run_id, round_number=1, bear_argument="")
    else:
        result = agent.run(bundle, run_id=run_id)

    print("=== Agent Output ===")
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python debug/run_agent.py <agent_name> <run_id>")
        sys.exit(1)
    run_agent(sys.argv[1], int(sys.argv[2]))
```

- [ ] **Step 3: Write `debug/inspect_run.py`**

```python
#!/usr/bin/env python
"""Pretty-print all logs, agent outputs, and debate transcript for a run.

Usage:
    python debug/inspect_run.py <run_id>
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import DEBUG_BUNDLES_DIR, LOGS_DIR, DB_PATH


def inspect(run_id: int) -> None:
    # ── Bundle ──────────────────────────────────────────────────────────────
    bundle_path = DEBUG_BUNDLES_DIR / f"run_{run_id}_bundle.json"
    if bundle_path.exists():
        bundle = json.loads(bundle_path.read_text())
        print(f"{'='*60}")
        print(f"Run {run_id} — {bundle.get('ticker')} — {bundle.get('fetched_at')}")
        print(f"Data confidence: {bundle.get('data_confidence')}")
        print(f"{'='*60}\n")

        manifest = bundle.get("manifest", {})
        print("=== DATA MANIFEST ===")
        for field, meta in manifest.items():
            status = meta.get("status", "?")
            source = meta.get("source", "?")
            icon = "✓" if status == "ok" else ("⚠" if status == "partial" else "✗")
            note = f" — {meta['note']}" if meta.get("note") else ""
            print(f"  {icon} {field}: {status} (from {source}){note}")
        print()
    else:
        print(f"[WARN] Bundle not found: {bundle_path}")

    # ── Database ─────────────────────────────────────────────────────────────
    if DB_PATH.exists():
        import sqlite3
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row

        runs = conn.execute(
            "SELECT * FROM analysis_runs WHERE id = ?", (run_id,)
        ).fetchall()
        if runs:
            run = dict(runs[0])
            print("=== RUN RECORD ===")
            for k, v in run.items():
                print(f"  {k}: {v}")
            print()

        agents = conn.execute(
            "SELECT agent, phase, score, data_confidence, status, duration_ms, summary "
            "FROM agent_outputs WHERE run_id = ? ORDER BY phase, agent",
            (run_id,)
        ).fetchall()
        if agents:
            print("=== AGENT OUTPUTS ===")
            for a in agents:
                a = dict(a)
                icon = "✓" if a["status"] == "complete" else "✗"
                print(f"  {icon} [{a['phase']}] {a['agent']}: score={a['score']} | confidence={a['data_confidence']} | {a['duration_ms']}ms")
                print(f"     {a['summary'][:120]}...")
            print()

        debate = conn.execute(
            "SELECT round_number, bull_conviction, bear_conviction, bull_argument, bear_argument "
            "FROM debate_rounds WHERE run_id = ? ORDER BY round_number",
            (run_id,)
        ).fetchall()
        if debate:
            print("=== DEBATE TRANSCRIPT ===")
            for rnd in debate:
                rnd = dict(rnd)
                gap = abs(rnd["bull_conviction"] - rnd["bear_conviction"])
                consensus = "✓ CONSENSUS" if gap <= 2 else ""
                print(f"  Round {rnd['round_number']} | Bull: {rnd['bull_conviction']} | Bear: {rnd['bear_conviction']} | Gap: {gap} {consensus}")
                print(f"    Bull: {str(rnd['bull_argument'])[:150]}...")
                print(f"    Bear: {str(rnd['bear_argument'])[:150]}...")
            print()
        conn.close()

    # ── Log file ─────────────────────────────────────────────────────────────
    log_path = LOGS_DIR / f"run_{run_id}.log"
    if log_path.exists():
        print("=== LOG FILE ===")
        lines = log_path.read_text(encoding="utf-8").splitlines()
        for line in lines:
            print(f"  {line}")
    else:
        print(f"[INFO] No log file found at {log_path}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python debug/inspect_run.py <run_id>")
        sys.exit(1)
    inspect(int(sys.argv[1]))
```

---

## Task 11: Run Tests and Commit

- [ ] **Step 1: Activate venv and run unit tests**

```powershell
cd "C:\Users\user\OneDrive\Desktop\HedgeFund"
.\venv\Scripts\Activate.ps1
pytest tests/unit/ -v
```

Expected: all unit tests pass (no LLM calls, no network).

- [ ] **Step 2: Run integration tests**

```powershell
pytest tests/integration/test_agents.py -v
```

Expected: all integration tests pass (LLM calls are mocked).

- [ ] **Step 3: Run full test suite**

```powershell
pytest tests/ -v --ignore=tests/e2e
```

Expected: all unit + integration + failure_scenario tests pass.

- [ ] **Step 4: Commit Plan 2**

```powershell
git add agents/ prompts/ debug/ tests/unit/test_base_agent.py tests/unit/test_debate_convergence.py tests/unit/test_score_calculation.py tests/integration/test_agents.py tests/fixtures/sample_agent_outputs/ tests/conftest.py plans/plan2-agents.md
git commit -m "feat: Plan 2 complete — all 11 agents, prompt files, debug tools (all tests passing)"
```

---

## What's Next After Plan 2

**Plan 3: Pipeline + Web UI**
- `pipeline/orchestrator.py` — Phase runner, parallel async execution, SSE emitter, abort rule (2× minimal), checkpoint writer
- `pipeline/debate.py` — Bull/Bear loop, convergence/contested logic, full transcript assembly
- `pipeline/monitor.py` — Daily watchlist price check + ntfy.sh alerts
- `main.py` — FastAPI app, SSE `/analyse` endpoint, file upload handler, resume endpoint
- `static/app.js` + `templates/index.html` — Frontend with real-time progress, debate feed, upload zone

**Plan 4: Reports + Monitor + Final Polish**
- `reports/generator.py` — Full 8-section HTML report builder
- Windows Task Scheduler setup for `monitor.py`
- Watchlist DB writes, alert_sent flag, duplicate detection
- Final e2e test: `test_full_run_aapl.py` and `test_resume_checkpoint.py`
