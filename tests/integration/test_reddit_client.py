# tests/integration/test_reddit_client.py
import pytest
from unittest.mock import patch, MagicMock
from data.reddit_client import RedditClient


def _make_post(title, score, url, selftext=""):
    p = MagicMock()
    p.title = title
    p.score = score
    p.url = url
    p.selftext = selftext
    p.created_utc = 1746873600.0
    p.num_comments = 42
    return p


def test_get_posts_returns_structured_results():
    mock_reddit = MagicMock()
    sub = MagicMock()
    sub.search.return_value = [
        _make_post("AAPL to $300 by EOY", 2500, "https://reddit.com/r/wallstreetbets/1"),
        _make_post("Apple earnings analysis", 800, "https://reddit.com/r/investing/2"),
    ]
    mock_reddit.subreddit.return_value = sub
    with patch("data.reddit_client.praw.Reddit", return_value=mock_reddit):
        client = RedditClient(client_id="x", client_secret="y", user_agent="test")
        result = client.get_posts("AAPL", subreddits=["wallstreetbets"], limit=10)
    assert result["total_posts"] == 2
    assert result["posts"][0]["score"] == 2500
    assert result["source"] == "reddit"


def test_get_posts_empty_on_error():
    with patch("data.reddit_client.praw.Reddit", side_effect=Exception("auth failed")):
        client = RedditClient(client_id="x", client_secret="y", user_agent="test")
        result = client.get_posts("AAPL")
    assert result["total_posts"] == 0
    assert "error" in result


def test_sentiment_summary_counts_keywords():
    from data.reddit_client import _score_sentiment
    assert _score_sentiment("AAPL is going to the moon, bullish AF") == "positive"
    assert _score_sentiment("AAPL is crashing, bearish, puts printing") == "negative"
    assert _score_sentiment("I own AAPL shares") == "neutral"
