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
