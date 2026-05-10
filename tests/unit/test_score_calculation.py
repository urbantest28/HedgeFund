"""Tests for portfolio manager score interpretation."""

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
    for score in range(1, 6):
        assert score in SCORE_LABELS
        assert score in SCORE_VERDICTS


def test_out_of_range_score_not_in_labels():
    assert 0 not in SCORE_LABELS
    assert 6 not in SCORE_LABELS
