"""Tests for the probability engine — the 'real-solution' math."""

import math

from packages.risk.probability import (
    annualized_volatility,
    expected_value,
    horizon_to_days,
    realistic_entry_plan,
    till_date,
    touch_probability,
    trade_win_probability,
    _norm_cdf,
)


def run():
    assert abs(_norm_cdf(0.0) - 0.5) < 1e-9

    # touch_probability in [0,1], rises with vol, rises as target gets nearer.
    p = touch_probability(225, 210, 15, 0.30)
    assert 0.0 <= p <= 1.0, p
    assert touch_probability(225, 210, 15, 0.50) > p   # more vol -> more likely to reach
    assert touch_probability(225, 220, 15, 0.30) > p   # nearer -> more likely
    assert touch_probability(225, 150, 15, 0.30) < p   # far -> less likely

    # The exact NVDA-style case: "wait for a dip to 210 from 225" should NOT be
    # presented as likely. With 25% vol over ~3 weeks it is a long shot.
    p_nvda = touch_probability(225, 210, 15, 0.25)
    assert p_nvda < 0.5, p_nvda

    # trade_win_probability: 50/50 when reward:risk is 1:1 in log space.
    wp = trade_win_probability(100.0, 110.0, 100 / 1.1)   # tp +10%, stop -9.09%
    assert abs(wp - 0.5) < 1e-3, wp
    # Tighter stop (smaller risk) => lower chance to reach target first.
    assert trade_win_probability(100.0, 110.0, 98.0) < wp
    # Wider stop (more room) => higher chance to reach target first.
    assert trade_win_probability(100.0, 110.0, 85.0) > wp

    # expected_value: 1:1 reward:risk is +EV only when p > 0.5.
    assert abs(expected_value(0.5, 10.0, 10.0) - 0.0) < 1e-9
    assert expected_value(0.6, 10.0, 10.0) > 0
    assert expected_value(0.4, 10.0, 10.0) < 0

    # realistic_entry_plan — unlikely dip => 3-rung ladder, warn not to wait.
    plan = realistic_entry_plan(225, 210, 15, 0.25, direction="long")
    assert plan.likely_to_miss and plan.prob_reach_entry < 0.5, plan
    assert len(plan.ladders) == 3, plan.ladders
    assert plan.expected_entry is not None
    assert "Do NOT just wait" in plan.plain_language

    # Likely dip (high vol + near) => work the limit, 2 rungs, no miss warning.
    plan2 = realistic_entry_plan(225, 222, 20, 0.6, direction="long")
    assert not plan2.likely_to_miss and plan2.prob_reach_entry >= 0.5, plan2
    assert len(plan2.ladders) == 2, plan2.ladders

    # horizon / till-date plumbing
    assert horizon_to_days("SWING") == 15
    assert till_date(15).toordinal() > 0

    # annualized_volatility: flat series ~0, trending series > 0.
    assert annualized_volatility([100, 100, 100, 100]) < 1e-6
    assert annualized_volatility([100, 101, 102, 103, 104]) > 0

    print("test_probability: all passed")


if __name__ == "__main__":
    run()
