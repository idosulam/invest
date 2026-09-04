"""Structured Sentiment Analyst.

Inspired by TradingAgents' Sentiment Analyst: aggregates multiple data
sources (news sentiment, congressional trading, price momentum as a proxy
for social sentiment) into a single structured SentimentReport with
band, score, and confidence levels.

This replaces the free-text sentiment label on individual news articles
with a holistic, agent-level sentiment assessment.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.llm.ollama_client import OllamaClient
from packages.agents.schemas import SentimentBand, SentimentReport, render_sentiment_report
from packages.agents.structured import structured_chat
from packages.domain.entities.models import (
    Instrument, MarketBar, NewsArticle, CongressTradeRecord,
)
from packages.domain.enums.common import Timeframe

logger = logging.getLogger(__name__)


async def _gather_sentiment_data(db: AsyncSession, instrument: Instrument) -> dict:
    """Pull all sentiment-relevant data for the instrument."""

    # News with sentiment labels
    cutoff_14d = datetime.now(timezone.utc) - timedelta(days=14)
    news_result = await db.execute(
        select(NewsArticle)
        .where(NewsArticle.instrument_id == instrument.id, NewsArticle.published_at >= cutoff_14d)
        .order_by(NewsArticle.published_at.desc())
        .limit(20)
    )
    articles = news_result.scalars().all()

    # Aggregate news sentiment
    sentiment_counts = {"positive": 0, "negative": 0, "neutral": 0}
    news_lines = []
    for a in articles:
        label = (a.sentiment_label or "neutral").lower()
        if "pos" in label or "bull" in label:
            sentiment_counts["positive"] += 1
            direction = "🟢"
        elif "neg" in label or "bear" in label:
            sentiment_counts["negative"] += 1
            direction = "🔴"
        else:
            sentiment_counts["neutral"] += 1
            direction = "⚪"
        score_str = f" (score: {a.sentiment_score})" if a.sentiment_score else ""
        news_lines.append(
            f"- {direction} [{a.published_at.date()}] {a.title}{score_str}"
        )

    # Congressional trading (sentiment signal from smart money)
    cutoff_90d = datetime.now(timezone.utc) - timedelta(days=90)
    congress_result = await db.execute(
        select(CongressTradeRecord)
        .where(
            CongressTradeRecord.instrument_id == instrument.id,
            CongressTradeRecord.transaction_date >= cutoff_90d,
        )
        .order_by(CongressTradeRecord.transaction_date.desc())
        .limit(15)
    )
    trades = congress_result.scalars().all()
    buy_count = sum(1 for t in trades if t.trade_type.lower() == "buy")
    sell_count = sum(1 for t in trades if t.trade_type.lower() == "sell")
    congress_lines = [
        f"- {t.member_name} ({t.chamber}): {t.trade_type.upper()} {t.amount_range} on {t.transaction_date.date()}"
        for t in trades
    ] or ["No recent congressional trading activity."]

    # Price momentum as a proxy for market sentiment
    bars_result = await db.execute(
        select(MarketBar)
        .where(MarketBar.instrument_id == instrument.id, MarketBar.timeframe == Timeframe.DAILY)
        .order_by(MarketBar.ts_open.desc())
        .limit(20)
    )
    bars = list(reversed(bars_result.scalars().all()))
    momentum_lines = []
    if bars and len(bars) >= 5:
        first, last = bars[0], bars[-1]
        pct_5d = float((last.close - bars[-5].close) / bars[-5].close * 100) if bars[-5].close else 0
        pct_20d = float((last.close - first.close) / first.close * 100) if first.close else 0
        avg_vol = sum(float(b.volume) for b in bars) / len(bars)
        recent_vol = float(bars[-1].volume)
        vol_ratio = recent_vol / avg_vol if avg_vol > 0 else 1.0

        momentum_lines = [
            f"5-day return: {pct_5d:+.2f}%",
            f"20-day return: {pct_20d:+.2f}%",
            f"Volume ratio (latest / 20d avg): {vol_ratio:.2f}x",
            f"Current price: ${last.close}",
        ]

    return {
        "news_lines": news_lines,
        "sentiment_counts": sentiment_counts,
        "total_news": len(articles),
        "congress_lines": congress_lines,
        "congress_buy": buy_count,
        "congress_sell": sell_count,
        "congress_total": len(trades),
        "momentum_lines": momentum_lines,
    }


def _build_sentiment_prompt(data: dict, symbol: str) -> str:
    """Build the user prompt for the sentiment analyst LLM call."""
    news_section = "\n".join(data["news_lines"])
    congress_section = "\n".join(data["congress_lines"])
    momentum_section = "\n".join(data["momentum_lines"]) if data["momentum_lines"] else "Insufficient data."

    counts = data["sentiment_counts"]
    news_summary = (
        f"News sentiment breakdown: {counts['positive']} positive, "
        f"{counts['negative']} negative, {counts['neutral']} neutral "
        f"(out of {data['total_news']} articles in last 14 days)"
    )

    congress_summary = (
        f"Congressional activity (90d): {data['congress_buy']} buys, "
        f"{data['congress_sell']} sells out of {data['congress_total']} trades"
    )

    return (
        f"Analyze the overall market sentiment for {symbol} based on the "
        f"following data sources. Synthesize a holistic sentiment assessment.\n\n"
        f"=== NEWS SENTIMENT ===\n{news_summary}\n{news_section}\n\n"
        f"=== CONGRESSIONAL TRADING (Smart Money) ===\n{congress_summary}\n{congress_section}\n\n"
        f"=== PRICE MOMENTUM (Market Psychology Proxy) ===\n{momentum_section}\n\n"
        f"Provide your assessment as a JSON object."
    )


SENTIMENT_SYSTEM = (
    "You are a sentiment analyst at a trading firm. Your job is to aggregate "
    "multiple data sources into a single, actionable sentiment read.\n\n"
    "Data sources you have:\n"
    "1. NEWS: Headlines with sentiment labels from the last 14 days\n"
    "2. CONGRESSIONAL TRADING: Buy/sell activity from US politicians (smart money proxy)\n"
    "3. PRICE MOMENTUM: Recent price action and volume as market psychology proxy\n\n"
    "Your assessment must be:\n"
    "- Grounded in the specific data provided (cite counts, ratios, specific headlines)\n"
    "- Honest about confidence: if data is thin (few articles, no congress trades), say so\n"
    "- Actionable: the trading team needs to know if sentiment is leaning bullish or bearish\n\n"
    "For the overall_band field:\n"
    "- Bullish: all or most sources clearly positive\n"
    "- Mildly Bullish: majority positive but with some caution\n"
    "- Neutral: genuinely no directional lean\n"
    "- Mixed: sources clearly point in different directions\n"
    "- Mildly Bearish: majority negative but with some support\n"
    "- Bearish: all or most sources clearly negative\n\n"
    "For overall_score (0-10): 0=max bearish, 5=neutral, 10=max bullish.\n"
    "Guidelines: Bullish ~6.5-10, Mildly Bullish ~5.5-6.4, Neutral/Mixed ~4.5-5.5, "
    "Mildly Bearish ~3.5-4.4, Bearish ~0-3.4.\n\n"
    "For confidence: 'low' if <5 data points or one source missing, "
    "'medium' if data present but sparse, 'high' if all sources substantive."
)


async def analyze_sentiment(
    db: AsyncSession,
    instrument_id,
) -> tuple[SentimentReport, str]:
    """Run structured sentiment analysis.

    Args:
        db: Database session
        instrument_id: UUID of the instrument

    Returns:
        Tuple of (SentimentReport, rendered_markdown_string).
    """
    result = await db.execute(select(Instrument).where(Instrument.id == instrument_id))
    instrument = result.scalar_one_or_none()
    if not instrument:
        raise ValueError("Instrument not found")

    data = await _gather_sentiment_data(db, instrument)
    user_prompt = _build_sentiment_prompt(data, instrument.symbol)

    client = OllamaClient()

    report = structured_chat(
        client, SENTIMENT_SYSTEM, user_prompt,
        schema=SentimentReport,
        temperature=0.2,
    )

    if report is None:
        # Fallback: derive a basic sentiment from the data counts
        counts = data["sentiment_counts"]
        total = data["total_news"]
        if total == 0:
            band = SentimentBand.NEUTRAL
            score = 5.0
        else:
            pos_ratio = counts["positive"] / total
            neg_ratio = counts["negative"] / total
            if pos_ratio > 0.6:
                band = SentimentBand.BULLISH
                score = 7.0
            elif pos_ratio > 0.4:
                band = SentimentBand.MILDLY_BULLISH
                score = 6.0
            elif neg_ratio > 0.6:
                band = SentimentBand.BEARISH
                score = 3.0
            elif neg_ratio > 0.4:
                band = SentimentBand.MILDLY_BEARISH
                score = 4.0
            else:
                band = SentimentBand.MIXED if counts["positive"] > 0 and counts["negative"] > 0 else SentimentBand.NEUTRAL
                score = 5.0

        # Factor in congressional activity
        if data["congress_buy"] > data["congress_sell"] and data["congress_total"] >= 2:
            score = min(10.0, score + 0.5)
        elif data["congress_sell"] > data["congress_buy"] and data["congress_total"] >= 2:
            score = max(0.0, score - 0.5)

        confidence = "low" if total < 5 else ("medium" if total < 10 else "high")

        report = SentimentReport(
            overall_band=band,
            overall_score=score,
            confidence=confidence,
            narrative=(
                f"**News Sentiment** ({total} articles): "
                f"{counts['positive']} positive, {counts['negative']} negative, "
                f"{counts['neutral']} neutral.\n\n"
                f"**Congressional Trading** ({data['congress_total']} trades, 90d): "
                f"{data['congress_buy']} buys, {data['congress_sell']} sells.\n\n"
                f"**Price Momentum**: {'; '.join(data['momentum_lines']) if data['momentum_lines'] else 'Insufficient data.'}\n\n"
                f"*Note: LLM unavailable for detailed analysis — this is a rule-based fallback.*"
            ),
        )

    rendered = render_sentiment_report(report)
    return report, rendered
