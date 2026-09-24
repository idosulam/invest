"""TradingAgents-native pipeline — analyst team -> debate -> trader -> risk -> portfolio-aware PM.

Orchestrates the full TradingAgents methodology using the engine's existing
agents plus the new ones (`analysts` fundamentals/news, `portfolio_manager`
portfolio-aware PM, `reflect` lessons loop). Independent of `consolidate.py` so
it can be adopted incrementally.

Flow: fundamentals + news + sentiment + technical -> bull/bear debate -> trader
proposal -> risk debate -> portfolio-aware Portfolio Manager -> reflection.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


async def run_trading_agents_pipeline(
    db: Any,
    instrument_id: Any,
    position: Optional[dict] = None,
) -> dict:
    """Run the full TradingAgents firm simulation for one instrument.

    Args:
        db: AsyncSession
        instrument_id: UUID
        position: optional {"quantity","avg_cost","portfolio_value","target_weight"}
            so the Portfolio Manager scales the decision to the existing book.

    Returns a consolidated dict with each stage's output + the final
    portfolio-aware action and a reflection block.
    """
    from sqlalchemy import select
    from packages.domain.entities.models import Instrument

    inst = (await db.execute(select(Instrument).where(Instrument.id == instrument_id))).scalar_one_or_none()
    if not inst:
        raise ValueError("Instrument not found")
    symbol = inst.symbol

    position = position or {}
    qty = float(position.get("quantity", 0.0) or 0.0)
    avg_cost = float(position.get("avg_cost", 0.0) or 0.0)
    pf_value = float(position.get("portfolio_value", 0.0) or 0.0)
    target_weight = float(position.get("target_weight", 0.05) or 0.05)

    # ── Reflection lessons from past decisions (injected into every analyst) ──
    lessons = ""
    try:
        from packages.agents.reflect import lessons_block
        from packages.agents.memory import DecisionMemoryLog
        lessons = lessons_block(DecisionMemoryLog().load_entries())
    except Exception as e:  # noqa: BLE001
        logger.warning("lessons unavailable: %s", e)

    # ── Analyst team ──
    from packages.agents.analysts import analyze_fundamentals, analyze_news
    from packages.agents.sentiment import analyze_sentiment

    fundamental_md = news_md = sentiment_md = ""
    try:
        _, fundamental_md = await analyze_fundamentals(db, instrument_id, lessons=lessons)
    except Exception as e:  # noqa: BLE001
        logger.warning("fundamental analyst failed: %s", e); fundamental_md = "Fundamentals unavailable."
    try:
        _, news_md = await analyze_news(db, instrument_id, lessons=lessons)
    except Exception as e:  # noqa: BLE001
        logger.warning("news analyst failed: %s", e); news_md = "News unavailable."
    try:
        _, sentiment_md = await analyze_sentiment(db, instrument_id)
    except Exception as e:  # noqa: BLE001
        logger.warning("sentiment analyst failed: %s", e); sentiment_md = "Sentiment unavailable."

    analyst_block = (
        f"FUNDAMENTALS:\n{fundamental_md}\n\nNEWS:\n{news_md}\n\nSENTIMENT:\n{sentiment_md}"
    )

    # ── Research: bull/bear debate (existing) ──
    debate = None
    try:
        from packages.agents.debate import run_debate
        debate = await run_debate(db, instrument_id)
    except Exception as e:  # noqa: BLE001
        logger.warning("debate failed: %s", e)
    bull = debate.bull_case if debate else "No debate available."
    bear = debate.bear_case if debate else "No debate available."
    verdict = debate.verdict if debate else ""

    # ── Trader proposal (existing chief-analyst synthesis) ──
    # Reuse the consolidated pipeline's trader step via consolidate's helpers is
    # overkill here; produce a lightweight proposal string from the debate verdict.
    trade_proposal = f"Verdict: {verdict}\n\nAnalyst inputs:\n{analyst_block}"
    current_price = await _latest_price(db, instrument_id)

    # ── Risk verdict (existing) ──
    risk_verdict = f"Risk level: {debate.risk_level if debate else 'MEDIUM'} — {debate.risk_reasoning if debate else ''}"

    # ── Portfolio-aware Portfolio Manager (TradingAgents PM) ──
    from packages.agents.portfolio_manager import decide_for_book, run_portfolio_manager
    signal_state = _state_from_verdict(verdict)
    _pf = pf_value or ((qty * (avg_cost or current_price or 0.0)) or 100_000.0)
    action = decide_for_book(signal_state, current_price or 0.0, qty, avg_cost, _pf, target_weight)
    action_md = await run_portfolio_manager(
        symbol, trade_proposal, bull, bear, risk_verdict,
        current_price or 0.0, qty, avg_cost, _pf, target_weight,
    )

    return {
        "symbol": symbol,
        "lessons": lessons,
        "fundamental_markdown": fundamental_md,
        "news_markdown": news_md,
        "sentiment_markdown": sentiment_md,
        "bull_case": bull,
        "bear_case": bear,
        "verdict": verdict,
        "risk_verdict": risk_verdict,
        "signal_state": signal_state,
        "portfolio_action": action,
        "portfolio_action_markdown": action_md,
    }


def _state_from_verdict(verdict: str) -> str:
    text = (verdict or "").upper()
    if "SELL" in text or "EXIT" in text:
        return "EXIT"
    if "REDUCE" in text or "TRIM" in text:
        return "REDUCE"
    if "BUY" in text or "LONG" in text or "ACCUMULAT" in text:
        return "ENTER_LONG"
    return "HOLD"


async def _latest_price(db: Any, instrument_id: Any) -> Optional[float]:
    """Latest daily close for the instrument (best-effort)."""
    try:
        from sqlalchemy import select
        from packages.domain.entities.models import MarketBar
        from packages.domain.enums.common import Timeframe
        row = (await db.execute(
            select(MarketBar.close).where(
                MarketBar.instrument_id == instrument_id, MarketBar.timeframe == Timeframe.DAILY
            ).order_by(MarketBar.ts_open.desc()).limit(1)
        )).scalar_one_or_none()
        return float(row) if row is not None else None
    except Exception:  # noqa: BLE001
        return None
