"""Tests for the deterministic fundamental/news analyst scoring (pure)."""

from packages.agents.analysts import (
    FundamentalBand,
    NewsBand,
    assess_fundamentals,
    assess_news_flow,
    classify_label,
    fundamental_band_for_score,
    metric_value,
    render_fundamental_report,
    render_news_report,
)


def run():
    # classify_label
    assert classify_label("positive") == "positive"
    assert classify_label("Bullish") == "positive"
    assert classify_label("bearish") == "negative"
    assert classify_label(None) == "neutral"

    # metric_value handles plain + record forms.
    assert metric_value({"roe": 0.2}, "roe") == 0.2
    assert metric_value({"roe": {"value": 0.2}}, "roe") == 0.2
    assert metric_value({}, "roe") is None

    # fundamental band mapping.
    assert fundamental_band_for_score(8.0) is FundamentalBand.STRONG
    assert fundamental_band_for_score(5.0) is FundamentalBand.NEUTRAL
    assert fundamental_band_for_score(1.0) is FundamentalBand.DISTRESSED

    # Strong fundamentals (profitable, low leverage) -> high score / good band.
    band, score, rationale = assess_fundamentals(
        {"profit_margin": 0.30, "roe": 0.25, "debt_to_equity": 0.3, "current_ratio": 2.0}
    )
    assert score > 7.0 and band in (FundamentalBand.STRONG, FundamentalBand.SOUND), (band, score)
    assert "profit margin" in rationale

    # Weak fundamentals -> low score / weak band.
    band2, score2, _ = assess_fundamentals({"profit_margin": -0.05, "roe": -0.1, "debt_to_equity": 3.0})
    assert score2 < 4.0 and band2 in (FundamentalBand.WEAK, FundamentalBand.DISTRESSED, FundamentalBand.NEUTRAL), (band2, score2)

    # Empty -> neutral.
    assert assess_fundamentals({})[0] is FundamentalBand.NEUTRAL

    # News flow: mostly positive -> bullish-ish, high score.
    pos = [{"sentiment_label": "positive", "sentiment_score": 0.5} for _ in range(5)]
    nb, ns, nr = assess_news_flow(pos)
    assert nb in (NewsBand.BULLISH, NewsBand.MILDLY_BULLISH) and ns > 5.0, (nb, ns)
    assert "positive" in nr

    # Mixed -> Mixed band.
    mix = [{"sentiment_label": "positive"}, {"sentiment_label": "negative"}]
    assert assess_news_flow(mix)[0] is NewsBand.MIXED

    # Empty news -> neutral.
    assert assess_news_flow([])[0] is NewsBand.NEUTRAL

    # Renderers surface band + score.
    class _R:
        band = FundamentalBand.STRONG; score = 8.0; confidence = "high"; narrative = "solid balance sheet"
    rf = render_fundamental_report(_R())
    assert "Strong" in rf and "8.0" in rf and "solid balance sheet" in rf

    class _N:
        band = NewsBand.BULLISH; score = 7.0; confidence = "medium"; narrative = "product cycle"; dominant_themes = "AI, margins"
    rn = render_news_report(_N())
    assert "Bullish" in rn and "AI, margins" in rn

    print("test_analysts: all passed")


if __name__ == "__main__":
    run()
