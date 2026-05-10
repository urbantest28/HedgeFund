"""Unit tests for debate convergence logic."""


def gap(bull_conv: int, bear_conv: int) -> int:
    return abs(bull_conv - bear_conv)


def test_gap_le_2_is_consensus():
    assert gap(7, 6) <= 2
    assert gap(8, 7) <= 2
    assert gap(6, 8) <= 2


def test_gap_gt_2_is_contested():
    assert gap(8, 5) > 2
    assert gap(9, 4) > 2
    assert gap(3, 9) > 2


def test_gap_boundary_exactly_2():
    assert gap(7, 5) == 2
    assert gap(5, 7) == 2


def test_contested_after_max_rounds():
    rounds = [
        {"bull_conviction": 8, "bear_conviction": 5},
        {"bull_conviction": 8, "bear_conviction": 5},
        {"bull_conviction": 8, "bear_conviction": 5},
        {"bull_conviction": 8, "bear_conviction": 5},
    ]
    for r in rounds:
        assert gap(r["bull_conviction"], r["bear_conviction"]) > 2
    assert len(rounds) == 4


def test_early_consensus_ends_debate():
    rounds = [
        {"bull_conviction": 8, "bear_conviction": 5},
        {"bull_conviction": 7, "bear_conviction": 6},
    ]
    ended_at = None
    for i, r in enumerate(rounds):
        if gap(r["bull_conviction"], r["bear_conviction"]) <= 2:
            ended_at = i + 1
            break
    assert ended_at == 2


def test_dominant_score_is_higher_conviction():
    bull_final = 8
    bear_final = 5
    dominant = bull_final if bull_final > bear_final else bear_final
    assert dominant == 8
