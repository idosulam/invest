"""Tests for the decision-log reflect/lessons loop."""

from packages.agents.reflect import (
    derive_lessons,
    format_lessons,
    lessons_block,
    score_decisions,
)


def run():
    entries = [
        {"symbol": "NVDA", "date": "2026-09-01", "state": "ENTER_LONG",
         "alpha_return": 0.032, "raw_return": 0.05, "holding_days": 5,
         "reflection": "momentum follow-through worked"},
        {"symbol": "TSLA", "date": "2026-09-02", "state": "ENTER_LONG",
         "alpha_return": -0.011, "raw_return": -0.02, "holding_days": 5,
         "reflection": "chased an extended spike"},
        {"symbol": "AAPL", "date": "2026-09-10", "state": "HOLD", "pending": True},
    ]

    s = score_decisions(entries)
    assert s["resolved"] == 2, s
    assert abs(s["hit_rate"] - 0.5) < 1e-9, s
    assert s["avg_alpha_pct"] is not None and s["avg_raw_pct"] is not None

    fl = format_lessons(entries)
    assert "NVDA" in fl and "worked" in fl
    assert "TSLAAPL" not in fl and "underperformed" in fl and "pending" in fl, fl
    assert "momentum follow-through worked" in fl  # reflection surfaced

    dl = derive_lessons(entries)
    assert any("50%" in d for d in dl), dl

    lb = lessons_block(entries)
    assert "KEY LESSONS" in lb and "RECENT DECISION HISTORY" in lb

    # Empty / edge cases.
    assert format_lessons([]) == ""
    assert score_decisions([])["resolved"] == 0
    assert derive_lessons([]) == []
    assert lessons_block([]) == ""

    print("test_reflect: all passed")


if __name__ == "__main__":
    run()
