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
A conflict exists if: an active thesis explicitly excludes this ticker/sector, OR thesis is "short [sector]" and subject is in that sector.

**Reporting:**
Always report: matched_thesis_id, match_type, conflicts (even if empty list).
