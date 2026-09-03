"""Bull / Bear / Judge agent debate.

Three LLM calls reason over the same evidence (recent price action,
news + sentiment, congressional trades) from opposite starting
positions, then a neutral judge weighs both arguments and produces
a plain-language recommendation with a qualitative risk level.

This is NOT a statistical probability estimate — no backtested edge
sits behind these numbers. It is a structured way to surface the
strongest case on each side plus a reasoned synthesis, framed
honestly as reasoning, not as a calibrated forecast.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.llm.ollama_client import OllamaClient
from packages.domain.entities.models import (
    Instrument, MarketBar, NewsArticle, CongressTradeRecord,
)
from packages.domain.enums.common import Timeframe

logger = logging.getLogger(__name__)


@dataclass
class DebateResult:
    symbol: str
    bull_case: str
    bear_case: str
    verdict: str
    risk_level: str
    risk_reasoning: str
    suggested_entry: str
    suggested_stop_loss: str
    suggested_take_profit: str
    evidence_summary: dict = field(default_factory=dict)


async def _gather_evidence(db: AsyncSession, instrument: Instrument) -> dict:
    bars_result = await db.execute(
        select(MarketBar)
        .where(MarketBar.instrument_id == instrument.id, MarketBar.timeframe == Timeframe.DAILY)
        .order_by(MarketBar.ts_open.desc())
        .limit(30)
    )
    bars = list(reversed(bars_result.scalars().all()))

    price_summary = "No price data available."
    if bars:
        first, last = bars[0], bars[-1]
        pct_change = float((last.close - first.close) / first.close * 100) if first.close else 0
        price_summary = (
            f"Over the last {len(bars)} trading days, {instrument.symbol} moved from "
            f"${first.close} to ${last.close} ({pct_change:+.2f}%). "
            f"Most recent close: ${last.close}, volume: {int(last.volume):,}."
        )

    cutoff = datetime.now(timezone.utc) - timedelta(days=14)
    news_result = await db.execute(
        select(NewsArticle)
        .where(NewsArticle.instrument_id == instrument.id, NewsArticle.published_at >= cutoff)
        .order_by(NewsArticle.published_at.desc())
        .limit(10)
    )
    articles = news_result.scalars().all()
    news_lines = [
        f"- [{a.published_at.date()}] ({a.sentiment_label or 'N/A'}) {a.title}"
        for a in articles
    ] or ["No recent news found."]

    cutoff90 = datetime.now(timezone.utc) - timedelta(days=90)
    congress_result = await db.execute(
        select(CongressTradeRecord)
        .where(CongressTradeRecord.instrument_id == instrument.id, CongressTradeRecord.transaction_date >= cutoff90)
        .order_by(CongressTradeRecord.transaction_date.desc())
        .limit(10)
    )
    trades = congress_result.scalars().all()
    congress_lines = [
        f"- {t.member_name} ({t.chamber}): {t.trade_type.upper()} {t.amount_range} on {t.transaction_date.date()}"
        for t in trades
    ] or ["No recent congressional trading activity found."]

    return {
        "price_summary": price_summary,
        "news_lines": news_lines,
        "congress_lines": congress_lines,
        "bars_count": len(bars),
        "news_count": len(articles),
        "congress_count": len(trades),
    }


def _build_evidence_block(evidence: dict) -> str:
    return (
        f"PRICE ACTION:\n{evidence['price_summary']}\n\n"
        f"RECENT NEWS (last 14 days):\n" + "\n".join(evidence["news_lines"]) + "\n\n"
        f"CONGRESSIONAL TRADING (last 90 days):\n" + "\n".join(evidence["congress_lines"])
    )


async def run_debate(db: AsyncSession, instrument_id) -> DebateResult:
    result = await db.execute(select(Instrument).where(Instrument.id == instrument_id))
    instrument = result.scalar_one_or_none()
    if not instrument:
        raise ValueError("Instrument not found")

    evidence = await _gather_evidence(db, instrument)
    evidence_block = _build_evidence_block(evidence)

    client = OllamaClient()

    bull_system = (
        "You are a bullish equity analyst. Given the evidence below, build the "
        "strongest honest case for BUYING or HOLDING this stock. Cite specific "
        "facts from the evidence. Do not invent facts not present in the evidence. "
        "If the evidence is weak or thin, say so plainly rather than overstating "
        "your case. Keep it to 3-5 sentences."
    )
    bear_system = (
        "You are a bearish equity analyst. Given the evidence below, build the "
        "strongest honest case for SELLING or AVOIDING this stock. Cite specific "
        "facts from the evidence. Do not invent facts not present in the evidence. "
        "If the evidence is weak or thin, say so plainly rather than overstating "
        "your case. Keep it to 3-5 sentences."
    )

    try:
        bull_case = client.chat(bull_system, evidence_block)
    except RuntimeError as e:
        bull_case = f"(Bull agent unavailable: {e})"

    try:
        bear_case = client.chat(bear_system, evidence_block)
    except RuntimeError as e:
        bear_case = f"(Bear agent unavailable: {e})"

    judge_system = (
        "You are a neutral risk analyst with no prior opinion on this stock. "
        "You will be given a bull case, a bear case, and the underlying evidence. "
        "Weigh both arguments on their merits — do not automatically split the "
        "difference. Then respond in EXACTLY this format, nothing else:\n\n"
        "VERDICT: <one or two sentences, plain language, what a reasonable "
        "investor should do and why>\n"
        "RISK_LEVEL: <LOW, MEDIUM, or HIGH>\n"
        "RISK_REASONING: <one or two sentences explaining the risk level — "
        "e.g. thin evidence, conflicting signals, high volatility>\n"
        "SUGGESTED_ENTRY: <ALWAYS give concrete guidance, even if the verdict "
        "is not to buy right now. If bullish: a price level or condition that "
        "would make entry attractive. If bearish or neutral: the specific price "
        "level, event, or condition that would need to change before this "
        "becomes attractive (e.g. 'a pullback to $X' or 'confirmation of Y "
        "trend' or 'stronger volume/news catalyst'). Never say Not applicable.>\n"
        "SUGGESTED_STOP_LOSS: <ALWAYS give a concrete price level or condition "
        "that would mean the thesis was wrong and you should sell to limit "
        "losses. If not long, describe what would confirm avoiding/shorting "
        "is correct. Never say Not applicable.>\n"
        "SUGGESTED_TAKE_PROFIT: <ALWAYS give a concrete price level, percentage "
        "gain, or condition (e.g. reaching a prior high, a specific resistance "
        "level, or a valuation getting stretched) at which a holder should sell "
        "to realize gains if the trade goes well. Be specific with a number or "
        "level where the evidence supports one. Never say Not applicable.>\n\n"
        "Do not present RISK_LEVEL as a numeric probability — it is a qualitative "
        "judgment, not a statistical forecast."
    )
    judge_user = (
        f"{evidence_block}\n\n"
        f"BULL CASE:\n{bull_case}\n\n"
        f"BEAR CASE:\n{bear_case}"
    )

    try:
        judge_response = client.chat(judge_system, judge_user, temperature=0.2)
    except RuntimeError as e:
        judge_response = (
            f"VERDICT: Unable to reach the local LLM ({e}).\n"
            "RISK_LEVEL: MEDIUM\n"
            "RISK_REASONING: No synthesis available — judge agent unavailable.\n"
            "SUGGESTED_ENTRY: Cannot assess — local LLM unreachable, no analysis possible right now.\n"
            "SUGGESTED_STOP_LOSS: Cannot assess — local LLM unreachable, no analysis possible right now.\n"
            "SUGGESTED_TAKE_PROFIT: Cannot assess — local LLM unreachable, no analysis possible right now."
        )

    parsed = _parse_judge_response(judge_response)

    return DebateResult(
        symbol=instrument.symbol,
        bull_case=bull_case,
        bear_case=bear_case,
        verdict=parsed["verdict"],
        risk_level=parsed["risk_level"],
        risk_reasoning=parsed["risk_reasoning"],
        suggested_entry=parsed["suggested_entry"],
        suggested_stop_loss=parsed["suggested_stop_loss"],
        suggested_take_profit=parsed["suggested_take_profit"],
        evidence_summary={
            "bars_count": evidence["bars_count"],
            "news_count": evidence["news_count"],
            "congress_count": evidence["congress_count"],
        },
    )


def _parse_judge_response(text: str) -> dict:
    fields = {
        "verdict": "", "risk_level": "MEDIUM", "risk_reasoning": "",
        "suggested_entry": "", "suggested_stop_loss": "", "suggested_take_profit": "",
    }
    key_map = {
        "VERDICT": "verdict",
        "RISK_LEVEL": "risk_level",
        "RISK_REASONING": "risk_reasoning",
        "SUGGESTED_ENTRY": "suggested_entry",
        "SUGGESTED_STOP_LOSS": "suggested_stop_loss",
        "SUGGESTED_TAKE_PROFIT": "suggested_take_profit",
    }
    for line in text.splitlines():
        line = line.strip()
        for prefix, key in key_map.items():
            if line.upper().startswith(prefix + ":"):
                fields[key] = line.split(":", 1)[1].strip()
                break

    if fields["risk_level"].upper() not in ("LOW", "MEDIUM", "HIGH"):
        fields["risk_level"] = "MEDIUM"
    else:
        fields["risk_level"] = fields["risk_level"].upper()

    if not fields["verdict"]:
        fields["verdict"] = text[:500]

    return fields
