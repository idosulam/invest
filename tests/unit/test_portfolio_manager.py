"""Tests for the portfolio-aware Portfolio Manager (pure logic)."""

from packages.agents.portfolio_manager import (
    assess_position,
    decide_for_book,
    render_pm_action,
)


def run():
    # qty 100 @ price 100 = 10k = 10% weight vs 5% target; avg_cost 90 -> +11%.
    a = assess_position(100, 100, 90, 100_000, 0.05)
    assert a.has_position and a.over_target, a
    assert abs(a.pnl_pct - (100 / 90 - 1)) < 1e-3, a

    # Overweight + winner + bullish -> TRIM into strength (Underweight rating).
    d = decide_for_book("ENTER_LONG", 100, 100, 90, 100_000, 0.05)
    assert d["action"] == "TRIM" and d["rating"] == "Underweight" and d["trade_value"] < 0, d

    # No position + bullish -> INITIATE (Buy rating).
    d2 = decide_for_book("ENTER_LONG", 100, 0, 0, 100_000, 0.05)
    assert d2["action"] == "INITIATE" and d2["rating"] == "Buy", d2

    # Exit signal with a holding -> EXIT (Sell rating).
    d3 = decide_for_book("EXIT", 100, 100, 90, 100_000, 0.05)
    assert d3["action"] == "EXIT" and d3["rating"] == "Sell", d3

    r = render_pm_action(d2)
    assert "Buy" in r and "INITIATE" in r and "Vs entry" in r, r

    print("test_portfolio_manager: all passed")


if __name__ == "__main__":
    run()
