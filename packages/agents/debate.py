"""Bull / Bear / Judge agent debate — multi-round with structured output.

Inspired by TradingAgents' researcher team architecture:
1. Bull and Bear researchers argue across multiple rounds (configurable)
2. Each round, each side sees the other's latest argument and responds
3. A Research Manager judge synthesizes the debate into a structured verdict

The multi-round approach surfaces stronger arguments because each side
must directly counter the other's points rather than just listing data.

Two layers of structured output:
- JudgeVerdict: typed Pydantic model from the judge (no regex parsing)
- DebateResult: full debate artifact with all rounds preserved
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.llm.ollama_client import OllamaClient
from packages.agents.schemas import (
    DebateResult,
    JudgeVerdict,
    RiskLevel,
)
from packages.agents.structured import structured_chat
from packages.data.providers.fred import get_macro_evidence_block
from packages.domain.entities.models import (
    Instrument, MarketBar, NewsArticle, CongressTradeRecord,
)
from packages.domain.enums.common import Timeframe

logger = logging.getLogger(__name__)

# Default number of debate rounds. Each round = one bull argument + one bear argument.
DEFAULT_DEBATE_ROUNDS = 2


async def _gather_evidence(db: AsyncSession, instrument: Instrument) -> dict:
    """Pull price action, news, and congressional trading data."""
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
        high_30 = max(float(b.high) for b in bars)
        low_30 = min(float(b.low) for b in bars)
        avg_vol = sum(float(b.volume) for b in bars) / len(bars)
        price_summary = (
            f"Over the last {len(bars)} trading days, {instrument.symbol} moved from "
            f"${first.close} to ${last.close} ({pct_change:+.2f}%). "
            f"30-day range: ${low_30:.2f} — ${high_30:.2f}. "
            f"Most recent close: ${last.close}, avg volume: {int(avg_vol):,}."
        )

    cutoff = datetime.now(timezone.utc) - timedelta(days=14)
    news_result = await db.execute(
        select(NewsArticle)
        .where(NewsArticle.instrument_id == instrument.id, NewsArticle.published_at >= cutoff)
        .order_by(NewsArticle.published_at.desc())
        .limit(15)
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
    # Include FRED macro data
    macro_block = get_macro_evidence_block()

    return (
        f"PRICE ACTION:\n{evidence['price_summary']}\n\n"
        f"RECENT NEWS (last 14 days):\n" + "\n".join(evidence["news_lines"]) + "\n\n"
        f"CONGRESSIONAL TRADING (last 90 days):\n" + "\n".join(evidence["congress_lines"]) + "\n\n"
        f"{macro_block}"
    )


def _build_bull_prompt(evidence_block: str, history: str, bear_latest: str) -> str:
    """Build the bull researcher's prompt for the current round."""
    if not bear_latest:
        return (
            f"You are a Bull Analyst advocating for BUYING this stock. "
            f"Build the strongest honest case using the evidence below. "
            f"Cite specific facts. If evidence is weak, say so plainly. "
            f"Keep it to 3-5 sentences.\n\n"
            f"EVIDENCE:\n{evidence_block}"
        )
    return (
        f"You are a Bull Analyst in a multi-round debate. The Bear Analyst "
        f"just argued against buying this stock. Counter their points with "
        f"specific evidence and reasoning. Address their concerns directly — "
        f"don't just repeat your opening argument. Keep it to 3-5 sentences.\n\n"
        f"EVIDENCE:\n{evidence_block}\n\n"
        f"DEBATE SO FAR:\n{history}\n\n"
        f"BEAR'S LATEST ARGUMENT:\n{bear_latest}"
    )


def _build_bear_prompt(evidence_block: str, history: str, bull_latest: str) -> str:
    """Build the bear researcher's prompt for the current round."""
    if not bull_latest:
        return (
            f"You are a Bear Analyst advocating for SELLING or AVOIDING this stock. "
            f"Build the strongest honest case using the evidence below. "
            f"Cite specific facts. If evidence is weak, say so plainly. "
            f"Keep it to 3-5 sentences.\n\n"
            f"EVIDENCE:\n{evidence_block}"
        )
    return (
        f"You are a Bear Analyst in a multi-round debate. The Bull Analyst "
        f"just argued for buying this stock. Counter their points with "
        f"specific evidence and reasoning. Address their concerns directly — "
        f"don't just repeat your opening argument. Keep it to 3-5 sentences.\n\n"
        f"EVIDENCE:\n{evidence_block}\n\n"
        f"DEBATE SO FAR:\n{history}\n\n"
        f"BULL'S LATEST ARGUMENT:\n{bull_latest}"
    )


JUDGE_SYSTEM = (
    "You are a neutral Research Manager synthesizing a bull/bear debate into "
    "a final verdict. You have no prior opinion on this stock. Weigh both "
    "arguments on their merits — do not automatically split the difference. "
    "The bull and bear have debated over multiple rounds; look for which side "
    "addressed the other's counterpoints more effectively.\n\n"
    "Respond with a JSON object with these fields:\n"
    '  "verdict": string — one or two sentences, plain language, what a reasonable investor should do and why\n'
    '  "risk_level": one of ["LOW", "MEDIUM", "HIGH"]\n'
    '  "risk_reasoning": string — one or two sentences explaining the risk level\n'
    '  "suggested_entry": string — ALWAYS give concrete guidance (price level, condition, or what needs to change)\n'
    '  "suggested_stop_loss": string — ALWAYS give a concrete price level or condition\n'
    '  "suggested_take_profit": string — ALWAYS give a concrete price level, percentage, or condition\n\n'
    "Return ONLY the JSON object."
)


def _parse_judge_text(text: str) -> JudgeVerdict:
    """Fallback: parse judge response from free text if JSON extraction fails."""
    fields = {
        "verdict": "", "risk_level": "MEDIUM", "risk_reasoning": "",
        "suggested_entry": "", "suggested_stop_loss": "", "suggested_take_profit": "",
    }
    key_map = {
        "VERDICT": "verdict", "RISK_LEVEL": "risk_level",
        "RISK_REASONING": "risk_reasoning", "SUGGESTED_ENTRY": "suggested_entry",
        "SUGGESTED_STOP_LOSS": "suggested_stop_loss", "SUGGESTED_TAKE_PROFIT": "suggested_take_profit",
    }
    for line in text.splitlines():
        line = line.strip()
        for prefix, key in key_map.items():
            if line.upper().startswith(prefix + ":"):
                fields[key] = line.split(":", 1)[1].strip()
                break

    try:
        return JudgeVerdict(**fields)
    except Exception:
        # Last resort: wrap the whole text as verdict
        return JudgeVerdict(
            verdict=text[:500],
            risk_level=RiskLevel.MEDIUM,
            risk_reasoning="Could not parse structured response.",
            suggested_entry="Unable to determine from available evidence.",
            suggested_stop_loss="Unable to determine from available evidence.",
            suggested_take_profit="Unable to determine from available evidence.",
        )


async def run_debate(
    db: AsyncSession,
    instrument_id,
    num_rounds: int = DEFAULT_DEBATE_ROUNDS,
) -> DebateResult:
    """Run a multi-round bull/bear debate and return structured result.

    Args:
        db: Database session
        instrument_id: UUID of the instrument to analyze
        num_rounds: Number of debate rounds (default: 2)

    Returns:
        DebateResult with all rounds preserved and structured judge verdict.
    """
    result = await db.execute(select(Instrument).where(Instrument.id == instrument_id))
    instrument = result.scalar_one_or_none()
    if not instrument:
        raise ValueError("Instrument not found")

    evidence = await _gather_evidence(db, instrument)
    evidence_block = _build_evidence_block(evidence)
    client = OllamaClient()

    # Multi-round debate
    bull_history = ""
    bear_history = ""
    bull_latest = ""
    bear_latest = ""

    for round_num in range(num_rounds):
        # Bull argues
        bull_prompt = _build_bull_prompt(evidence_block, bull_history, bear_latest)
        try:
            bull_response = client.chat(
                "You are a bullish equity analyst. Cite specific facts. Be concise.",
                bull_prompt,
                temperature=0.4,
            )
        except RuntimeError as e:
            bull_response = f"(Bull agent unavailable: {e})"

        bull_arg = f"[Round {round_num + 1}] Bull Analyst: {bull_response}"
        bull_latest = bull_response
        bull_history += ("\n" if bull_history else "") + bull_arg

        # Bear argues
        bear_prompt = _build_bear_prompt(evidence_block, bear_history, bull_latest)
        try:
            bear_response = client.chat(
                "You are a bearish equity analyst. Cite specific facts. Be concise.",
                bear_prompt,
                temperature=0.4,
            )
        except RuntimeError as e:
            bear_response = f"(Bear agent unavailable: {e})"

        bear_arg = f"[Round {round_num + 1}] Bear Analyst: {bear_response}"
        bear_latest = bear_response
        bear_history += ("\n" if bear_history else "") + bear_arg

    # Build full debate transcript for the judge
    full_debate = f"BULL CASE:\n{bull_history}\n\nBEAR CASE:\n{bear_history}"
    judge_user = f"{evidence_block}\n\n{full_debate}"

    # Judge with structured output
    judge = structured_chat(
        client, JUDGE_SYSTEM, judge_user,
        schema=JudgeVerdict,
        temperature=0.2,
    )

    if judge is None:
        # Fallback: try free-text parse
        try:
            raw_judge = client.chat(JUDGE_SYSTEM, judge_user, temperature=0.2)
            judge = _parse_judge_text(raw_judge)
        except RuntimeError:
            judge = JudgeVerdict(
                verdict="Unable to reach the LLM for synthesis.",
                risk_level=RiskLevel.MEDIUM,
                risk_reasoning="No synthesis available — judge agent unavailable.",
                suggested_entry="Cannot assess — LLM unreachable.",
                suggested_stop_loss="Cannot assess — LLM unreachable.",
                suggested_take_profit="Cannot assess — LLM unreachable.",
            )

    return DebateResult.from_judge(
        symbol=instrument.symbol,
        bull_case=bull_history,
        bear_case=bear_history,
        rounds=num_rounds,
        judge=judge,
        evidence={
            "bars_count": evidence["bars_count"],
            "news_count": evidence["news_count"],
            "congress_count": evidence["congress_count"],
        },
    )
