import praw
from typing import Any, Optional, List
from config import REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT
from logger import get_logger

log = get_logger("reddit")

BULLISH_WORDS = {"bull", "bullish", "moon", "buy", "calls", "long", "breakout", "undervalued"}
BEARISH_WORDS = {"bear", "bearish", "crash", "sell", "puts", "short", "overvalued", "dump"}


def _score_sentiment(text: str) -> str:
    words = set(text.lower().split())
    bull = len(words & BULLISH_WORDS)
    bear = len(words & BEARISH_WORDS)
    if bull > bear:
        return "positive"
    if bear > bull:
        return "negative"
    return "neutral"


class RedditClient:
    SUBREDDITS = ["wallstreetbets", "investing", "stocks"]

    def __init__(self, client_id: str = REDDIT_CLIENT_ID,
                 client_secret: str = REDDIT_CLIENT_SECRET,
                 user_agent: str = REDDIT_USER_AGENT):
        self._cid = client_id
        self._csec = client_secret
        self._ua = user_agent

    def get_posts(self, ticker: str,
                  subreddits: Optional[List[str]] = None,
                  limit: int = 50) -> dict:
        subs = subreddits or self.SUBREDDITS
        try:
            reddit = praw.Reddit(
                client_id=self._cid, client_secret=self._csec,
                user_agent=self._ua, read_only=True)
            all_posts = []
            for sub_name in subs:
                sub = reddit.subreddit(sub_name)
                for post in sub.search(ticker, limit=limit, sort="hot", time_filter="week"):
                    all_posts.append({
                        "title": post.title,
                        "score": post.score,
                        "url": post.url,
                        "subreddit": sub_name,
                        "created_utc": post.created_utc,
                        "num_comments": post.num_comments,
                        "sentiment": _score_sentiment(post.title + " " + post.selftext),
                    })
            all_posts.sort(key=lambda p: p["score"], reverse=True)
            pos = sum(1 for p in all_posts if p["sentiment"] == "positive")
            neg = sum(1 for p in all_posts if p["sentiment"] == "negative")
            log.info(f"Reddit {ticker}: {len(all_posts)} posts | +{pos} -{neg}")
            return {"posts": all_posts, "total_posts": len(all_posts),
                    "positive_count": pos, "negative_count": neg,
                    "source": "reddit"}
        except Exception as e:
            log.warning(f"Reddit get_posts({ticker}) failed: {e}")
            return {"posts": [], "total_posts": 0, "positive_count": 0,
                    "negative_count": 0, "source": "reddit", "error": str(e)}
