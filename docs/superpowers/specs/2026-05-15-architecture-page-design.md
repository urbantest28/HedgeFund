# Architecture Page Design — HedgeFund Analyser

**Date:** 2026-05-15  
**Purpose:** Standalone HTML page showcasing the app architecture for a personal development portfolio.

---

## Decisions

- **Style:** Light / Clean — white background, soft colour accents (indigo primary), professional and approachable
- **Detail level:** Medium — phases, agent names, data sources, tech stack, outputs. No API endpoint listing, no DB schema, no debug tooling.
- **Layout:** Top-down pipeline flow (A) — mirrors actual execution order, communicates phase sequencing and intra-phase parallelism naturally

---

## Page Structure

### 1. Hero
- Title: *HedgeFund Analyser*
- Subtitle: *A multi-agent AI system that simulates a hedge fund research desk to produce a scored investment verdict.*
- Three stat badges: `9 AI Agents`, `4 Phases`, `2 LLM Providers`
- Accent colour: indigo

### 2. Data Layer
- Six source pills in a horizontal row: yFinance, Alpha Vantage, SEC EDGAR, FRED, Reddit, Massive Market
- Label: "Data Layer"
- Note: *All data pre-fetched and bundled before agents run — results cached to reduce API calls.*
- Arrow pointing down into Phase 1

### 3. Pipeline — Phases 1–4 (centrepiece)
Each phase is a labelled block. Vertical stack with arrows between phases.

| Phase | Label | Agents | Model | Notes |
|---|---|---|---|---|
| 1 | Research | Fundamental, Technical, Sentiment, Macro, Earnings Reviewer | Gemini 2.0 Flash | Parallel; aborts if 2+ agents return minimal confidence |
| 2 | Validation | Risk Manager, Thesis Validator, Financial Modeler | Gemini 2.0 Flash | Parallel |
| 3 | Debate | Bull, Bear | Claude Opus 4.7 | Iterative loop with convergence check |
| 4 | Decision | Portfolio Manager | Claude Opus 4.7 | Produces final verdict + score |

Agent cards within each phase shown side by side (flex row). Each card: agent name + model badge.

### 4. Outputs
Three cards: HTML Report, Excel Model, Watchlist Entry.  
Tech stack strip: FastAPI · SQLite · SSE Streaming · Tailwind CSS · openpyxl · Python 3.9

---

## Deliverable

Single self-contained HTML file: `architecture.html` in the project root.  
No external dependencies — Tailwind via CDN only. No JS frameworks.
