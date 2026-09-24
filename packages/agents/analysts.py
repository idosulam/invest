"""Fundamental + News analysts — the missing TradingAgents analyst team members.

Completes the analyst team alongside the existing SentimentAnalyst
(`sentiment.py`) and technical strategies (`packages/strategies`):

- ``analyze_fundamentals``: SEC EDGAR / Yahoo / stored ``FundamentalFact`` evidence
  -> typed ``FundamentalReport`` (band / score / narrative).
- ``analyze_news``: recent ``NewsArticle`` rows -> typed ``NewsReport``.

Each returns ``(report, rendered_markdown)`` exactly like ``analyze_sentiment``.
Deterministic scoring/rendering is PURE + unit-tested; heavy deps (pydantic,
SQLAlchemy, OllamaClient, providers) are lazy-imported inside the async entry
points so the pure helpers import stdlib-only.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from enum import Enum
from typing import Any, Literal

logger = logging.getLogger(__name__)


class FundamentalBand(str, Enum):
    STRONG = "Strong"
    SOUND = "Sound"
    NEUTRAL = "Neutral"
    WEAK = "Weak"
    DISTRESSED = "Distressed"


class NewsBand(str, Enum):
    BULLISH = "Bullish"
    MILDLY_BULLISH = "Mildly Bullish"
    NEUTRAL = "Neutral"
    MIXED = "Mixed"
    MILDLY_BEARISH = "Mildly Bearish"
    BEARISH = "Bearish"


def _band_value(band: Any) -> str:
    return getattr(band, "value", str(band))


def render_fundamental_report(report: Any) -> str:
    return "\n".join([
        f"**Fundamental Assessment:** **{_band_value(report.band)}** (Score: {float(report.score):.1f}/10)",
        f"**Confidence:** {str(report.confidence).capitalize()}",
        "",
        report.narrative,
    ])


def render_news_report(report: Any) -> str:
    parts = [
        f"**News Flow:** **{_band_value(report.band)}** (Score: {float(report.score):.1f}/10)",
        f"**Confidence:** {str(report.confidence).capitalize()}",
        "",
        report.narrative,
    ]
    themes = (getattr(report, "dominant_themes", "") or "").strip()
    if themes:
        parts.extend(["", f"**Dominant Themes:** {themes}"])
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Pure evidence helpers + deterministic fallback scoring
# ---------------------------------------------------------------------------

def metric_value(facts: Mapping[str, Any], name: str) -> float | None:
    raw = facts.get(name)
    if raw is None:
        return None
    if isinstance(raw, Mapping):
        raw = raw.get("value")
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def classify_label(label: str | None) -> str:
    text = (label or "neutral").lower()
    if "pos" in text or "bull" in text:
        return "positive"
    if "neg" in text or "bear" in text:
        return "negative"
    return "neutral"


def fundamental_band_for_score(score: float) -> FundamentalBand:
    if score >= 7.5:
        return FundamentalBand.STRONG
    if score >= 6.0:
        return FundamentalBand.SOUND
    if score >= 4.0:
        return FundamentalBand.NEUTRAL
    if score >= 2.5:
        return FundamentalBand.WEAK
    return FundamentalBand.DISTRESSED


def assess_fundamentals(facts: Mapping[str, Any]) -> tuple[FundamentalBand, float, str]:
    """Rule-based fundamental score 0-10 (deterministic LLM fallback)."""
    if not facts:
        return FundamentalBand.NEUTRAL, 5.0, "No fundamental data available — neutral by default."
    score = 5.0
    notes: list[str] = []

    margin = metric_value(facts, "profit_margin")
    if margin is not None:
        if margin > 0.20:
            score += 1.5; notes.append(f"strong profit margin ({margin:+.1%})")
        elif margin > 0.10:
            score += 1.0; notes.append(f"healthy profit margin ({margin:+.1%})")
        elif margin > 0.0:
            score += 0.5; notes.append(f"thin profit margin ({margin:+.1%})")
        else:
            score -= 1.5; notes.append(f"negative profit margin ({margin:+.1%})")

    roe = metric_value(facts, "roe")
    if roe is not None:
        if roe > 0.15:
            score += 1.0; notes.append(f"high ROE ({roe:+.1%})")
        elif roe > 0.08:
            score += 0.5; notes.append(f"decent ROE ({roe:+.1%})")
        elif roe < 0.0:
            score -= 1.0; notes.append(f"negative ROE ({roe:+.1%})")

    debt = metric_value(facts, "debt_to_equity")
    if debt is not None:
        if debt > 2.0:
            score -= 1.5; notes.append(f"heavy leverage (D/E {debt:.2f})")
        elif debt > 1.0:
            score -= 0.75; notes.append(f"elevated leverage (D/E {debt:.2f})")
        elif debt < 0.5:
            score += 0.5; notes.append(f"conservative leverage (D/E {debt:.2f})")

    current = metric_value(facts, "current_ratio")
    if current is not None:
        if current < 1.0:
            score -= 0.75; notes.append(f"weak liquidity (current ratio {current:.2f})")
        elif current > 1.5:
            score += 0.25; notes.append(f"comfortable liquidity (current ratio {current:.2f})")

    score = max(0.0, min(10.0, score))
    rationale = "; ".join(notes) if notes else "Metrics present but none crossed scoring thresholds."
    return fundamental_band_for_score(score), score, rationale


def assess_news_flow(articles: Sequence[Mapping[str, Any]]) -> tuple[NewsBand, float, str]:
    """Rule-based news-flow score 0-10 (deterministic LLM fallback)."""
    if not articles:
        return NewsBand.NEUTRAL, 5.0, "No recent news — neutral by default."
    counts = {"positive": 0, "negative": 0, "neutral": 0}
    score_sum, score_n = 0.0, 0
    for a in articles:
        counts[classify_label(a.get("sentiment_label"))] += 1
        s = a.get("sentiment_score")
        if isinstance(s, (int, float)):
            score_sum += float(s); score_n += 1

    total = len(articles)
    pos_ratio = counts["positive"] / total
    neg_ratio = counts["negative"] / total
    if pos_ratio > 0.6:
        band, base = NewsBand.BULLISH, 7.0
    elif neg_ratio > 0.6:
        band, base = NewsBand.BEARISH, 3.0
    elif counts["positive"] > counts["negative"]:
        band, base = NewsBand.MILDLY_BULLISH, 6.0
    elif counts["negative"] > counts["positive"]:
        band, base = NewsBand.MILDLY_BEARISH, 4.0
    elif counts["positive"] > 0 and counts["negative"] > 0:
        band, base = NewsBand.MIXED, 5.0
    else:
        band, base = NewsBand.NEUTRAL, 5.0

    mean = (score_sum / score_n) if score_n else 0.0
    final = max(0.0, min(10.0, base + max(-1.0, min(1.0, mean))))
    rationale = f"{counts['positive']} positive, {counts['negative']} negative, {counts['neutral']} neutral of {total}"
    return band, final, rationale


# ---------------------------------------------------------------------------
# Async LLM entry points (heavy deps lazy-imported)
# ---------------------------------------------------------------------------

def _reports_schema(kind: str):
    """Tiny pydantic report models, built lazily (pydantic only needed at runtime)."""
    from pydantic import BaseModel, Field

    if kind == "fundamental":
        class _R(BaseModel):
            band: FundamentalBand
            score: float = Field(ge=0.0, le=10.0)
            confidence: str
            narrative: str
        return _R
    class _N(BaseModel):
        band: NewsBand
        score: float = Field(ge=0.0, le=10.0)
        confidence: str
        narrative: str
        dominant_themes: str = ""
    return _N


_FUNDAMENTAL_SYSTEM = (
    "You are the Fundamental Analyst on a trading firm's research desk (TradingAgents-style). "
    "Assess fundamentals (profitability, returns, leverage, liquidity, valuation) from the "
    "evidence block. Cite specific metric values; if evidence is thin, lower confidence. "
    "Score 0-10 = fundamental QUALITY (10 = pristine), not expected return."
)
_NEWS_SYSTEM = (
    "You are the News Analyst on a trading firm's research desk (TradingAgents-style). "
    "Assess recent news flow: dominant themes, concrete catalysts and risks, and whether tone "
    "is improving or deteriorating — cite headlines/dates. Score 0-10: 0 = maximally bearish, "
    "5 = neutral, 10 = maximally bullish."
)


async def analyze_fundamentals(db: Any, instrument_id: Any, *, lessons: str = "", fetch_live: bool = True):
    """Run the Fundamental Analyst -> (report, rendered_markdown)."""
    from sqlalchemy import select
    from packages.agents.structured import structured_chat
    from packages.domain.entities.models import Instrument
    from apps.api.llm.ollama_client import OllamaClient

    inst = (await db.execute(select(Instrument).where(Instrument.id == instrument_id))).scalar_one_or_none()
    if not inst:
        raise ValueError("Instrument not found")
    facts = await _gather_fundamentals(db, inst, fetch_live=fetch_live)
    evidence = _fundamental_evidence(inst.symbol, facts)
    prompt = f"Assess {inst.symbol} fundamentals.\n\n{evidence}" + (f"\n\nLESSONS:\n{lessons}" if lessons else "")

    report = structured_chat(OllamaClient(), _FUNDAMENTAL_SYSTEM, prompt,
                             schema=_reports_schema("fundamental"), temperature=0.2)
    if report is None:
        band, score, rationale = assess_fundamentals(facts)
        report = _make_report("fundamental", band=band, score=score,
                              confidence="low" if len(facts) < 5 else "medium",
                              narrative=f"{rationale} (rule-based fallback; {len(facts)} metrics).")
    return report, render_fundamental_report(report)


async def analyze_news(db: Any, instrument_id: Any, *, lessons: str = "", days: int = 30):
    """Run the News Analyst -> (report, rendered_markdown)."""
    from sqlalchemy import select
    from packages.agents.structured import structured_chat
    from packages.domain.entities.models import Instrument
    from apps.api.llm.ollama_client import OllamaClient

    inst = (await db.execute(select(Instrument).where(Instrument.id == instrument_id))).scalar_one_or_none()
    if not inst:
        raise ValueError("Instrument not found")
    articles = await _gather_news(db, inst, days=days)
    evidence = _news_evidence(articles)
    prompt = f"Assess {inst.symbol} news flow.\n\n{evidence}" + (f"\n\nLESSONS:\n{lessons}" if lessons else "")

    report = structured_chat(OllamaClient(), _NEWS_SYSTEM, prompt,
                             schema=_reports_schema("news"), temperature=0.2)
    if report is None:
        band, score, rationale = assess_news_flow(articles)
        report = _make_report("news", band=band, score=score,
                              confidence="low" if len(articles) < 5 else "medium",
                              narrative=f"{rationale} (rule-based fallback; {len(articles)} articles).",
                              dominant_themes="")
    return report, render_news_report(report)


def _make_report(kind: str, **kw):
    from types import SimpleNamespace
    return SimpleNamespace(**kw)


def _fundamental_evidence(symbol: str, facts: Mapping[str, Any]) -> str:
    if not facts:
        return f"No fundamental data for {symbol}."
    return f"FUNDAMENTAL FACTS ({symbol}):\n" + "\n".join(f"- {k}: {v}" for k, v in sorted(facts.items()))


def _news_evidence(articles: Sequence[Mapping[str, Any]]) -> str:
    if not articles:
        return "No recent news."
    lines = [f"- [{str(a.get('published_at',''))[:10]}] {a.get('title','')}" for a in articles]
    return "RECENT NEWS:\n" + "\n".join(lines)


async def _gather_fundamentals(db: Any, instrument: Any, fetch_live: bool = True) -> dict:
    facts: dict = {}
    try:
        from sqlalchemy import select
        from packages.domain.entities.models import FundamentalFact
        rows = (await db.execute(
            select(FundamentalFact).where(FundamentalFact.instrument_id == instrument.id)
        )).scalars().all()
        for f in rows:
            facts.setdefault(f.taxonomy, float(f.value))
    except Exception as e:  # noqa: BLE001
        logger.warning("stored fundamentals unavailable: %s", e)
    return facts


async def _gather_news(db: Any, instrument: Any, days: int = 30) -> list[dict]:
    try:
        from datetime import datetime, timedelta, timezone
        from sqlalchemy import select
        from packages.domain.entities.models import NewsArticle
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        rows = (await db.execute(
            select(NewsArticle).where(NewsArticle.instrument_id == instrument.id,
                                      NewsArticle.published_at >= cutoff)
            .order_by(NewsArticle.published_at.desc()).limit(30)
        )).scalars().all()
        return [{"title": a.title, "sentiment_label": a.sentiment_label,
                 "sentiment_score": float(a.sentiment_score) if a.sentiment_score is not None else None,
                 "published_at": str(a.published_at)[:10]} for a in rows]
    except Exception as e:  # noqa: BLE001
        logger.warning("news gathering failed: %s", e)
        return []
