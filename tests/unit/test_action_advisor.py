"""Tests for the portfolio-aware action advisor."""

from packages.portfolio.action_advisor import Action, PositionContext, recommend


def _ctx(qty=0.0, avg=0.0, price=100.0, port=100_000.0, tw=0.05):
    return PositionContext(current_price=price, portfolio_value=port,
                           quantity=qty, avg_cost=avg, target_weight=tw)


def run():
    # No position + bullish -> scaled INITIATE (half of a 5% target = $2500).
    d = recommend("ENTER_LONG", _ctx())
    assert d.action is Action.INITIATE and d.trade_value > 0, d
    assert abs(d.trade_value - 100_000 * 0.05 * 0.5) < 1e-6

    # No position + bearish -> AVOID; + HOLD -> WATCH.
    assert recommend("EXIT", _ctx()).action is Action.AVOID
    assert recommend("HOLD", _ctx()).action is Action.WATCH

    # Has position + bullish + underweight -> ADD (buy part).
    d = recommend("ENTER_LONG", _ctx(qty=2, avg=95, price=100, port=100_000, tw=0.05))
    assert d.action is Action.ADD and d.trade_value > 0, d

    # Has position + bullish + overweight + winner -> TRIM into strength (sell part).
    d = recommend("ENTER_LONG", _ctx(qty=100, avg=85, price=100, port=100_000, tw=0.05))
    assert d.action is Action.TRIM and d.trade_value < 0, d

    # REDUCE -> TRIM part (0 < fraction < 1).
    d = recommend("REDUCE", _ctx(qty=100, avg=90, price=100))
    assert d.action is Action.TRIM and 0 < d.trade_pct_of_position < 1, d

    # EXIT -> EXIT all.
    d = recommend("EXIT", _ctx(qty=100, avg=90, price=100))
    assert d.action is Action.EXIT and d.trade_pct_of_position == 1.0, d

    # Stop hit -> EXIT even on HOLD.
    d = recommend("HOLD", _ctx(qty=100, avg=90, price=100), stop_price=105)
    assert d.action is Action.EXIT, d

    # Normal HOLD (not concentrated, not a deep loser) -> HOLD, reports pnl vs entry.
    d = recommend("HOLD", _ctx(qty=30, avg=90, price=100))
    assert d.action is Action.HOLD and abs(d.pnl_pct - (100 / 90 - 1)) < 1e-3, d

    print("test_action_advisor: all passed")


if __name__ == "__main__":
    run()
