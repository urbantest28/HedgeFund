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
