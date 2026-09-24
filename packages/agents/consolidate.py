"""Consolidated signal — full multi-agent pipeline.

Architecture (inspired by TradingAgents):

1. SENTIMENT ANALYST — structured sentiment report (band + score + confidence)
2. TECHNICAL STRATEGIES — deterministic strategy signals with backtest win rates
3. BULL/BEAR DEBATE — multi-round debate informed by news + congress + sentiment
4. CHIEF ANALYST — synthesizes all inputs into a structured trade proposal
5. RISK DEBATE — aggressive/conservative/neutral debate on the proposal
6. PORTFOLIO MANAGER — final structured decision with 5-tier rating

Each layer uses structured Pydantic output so downstream consumers
never regex-parse prose.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.llm.ollama_client import OllamaClient
from packages.agents.debate import run_debate
from packages.agents.sentiment import analyze_sentiment
from packages.agents.risk_debate import run_risk_debate
from packages.agents.memory import DecisionMemoryLog
from packages.agents.resolver import resolve_pending_outcomes
from packages.agents.schemas import (
    ConsolidatedSignal,
    FinalState,
    PortfolioDecision,
    PortfolioRating,
    RiskLevel,
    SentimentReport,
    render_pm_decision,
    render_sentiment_report,
)
from packages.agents.structured import structured_chat
from packages.strategies.engine import generate_signals_for_instrument
from packages.domain.enums.common import SignalState
from packages.domain.entities.models import Instrument
from packages.risk import probability as _prob
from packages.portfolio.action_advisor import PositionContext as _Ctx, recommend as _recommend

logger = logging.getLogger(__name__)

# Rough directional weight per state, used only for the deterministic pre-vote.
_STATE_LEAN = {
    "ENTER_LONG": 1.0,
    "REDUCE": -0.5,
    "EXIT": -1.0,
    "HOLD": 0.0,
    "WATCH": 0.0,
    "NO_SIGNAL": 0.0,
}


def _deterministic_lean(technical_signals: list[dict]) -> tuple[float, int]:
    """Confidence-weighted average lean across strategies with a real signal."""
    total_weight = 0.0
    weighted_sum = 0.0
    counted = 0
    for s in technical_signals:
        if s.get("error") or s.get("state") in (None, "NO_SIGNAL"):
            continue
        conf = s.get("confidence") or 0.0
        lean = _STATE_LEAN.get(s.get("state"), 0.0)
        weighted_sum += lean * conf
        total_weight += conf
        counted += 1
    if total_weight == 0:
        return 0.0, counted
    return weighted_sum / total_weight, counted


async def _recent_closes(db: AsyncSession, instrument_id, limit: int = 90) -> list[float]:
    """Recent daily closes (oldest->newest) for a volatility estimate."""
    from sqlalchemy import select as _sel
    from packages.domain.entities.models import MarketBar as _MB
    from packages.domain.enums.common import Timeframe as _TF
    r = await db.execute(
        _sel(_MB.close)
        .where(_MB.instrument_id == instrument_id, _MB.timeframe == _TF.DAILY)
        .order_by(_MB.ts_open.desc())
        .limit(limit)
    )
    rows = [float(x[0]) for x in r.all()]
    rows.reverse()
    return rows


def _horizon_days_from(pm_decision) -> int:
    """Per-stock 'till when': horizon in trading days from the PM holding period."""
    txt = (getattr(pm_decision, "time_horizon", None) or "").lower()
    if "year" in txt:
        return 252
    if "month" in txt:
        nums = re.findall(r"\d+", txt)
        return min(252, (max(int(n) for n in nums) if nums else 6) * 21)
    if "week" in txt:
        nums = re.findall(r"\d+", txt)
        return max(5, (max(int(n) for n in nums) if nums else 3) * 5)
    if "day" in txt:
        return 5
    return 30


async def run_consolidated_analysis(
    db: AsyncSession,
    instrument_id,
    *,
    position_qty: float = 0.0,
    avg_cost: float = 0.0,
    portfolio_value: float = 0.0,
    target_weight: float = 0.05,
    stop_price: float | None = None,
) -> ConsolidatedSignal:
    """Run the full multi-agent analysis pipeline.

    Pipeline:
    1. Sentiment analysis (structured)
    2. Technical strategies (deterministic)
    3. Multi-round bull/bear debate (LLM)
    4. Chief analyst synthesis (structured)
    5. Risk debate (LLM)
    6. Portfolio manager final decision (structured)
    """
    from sqlalchemy import select
    from packages.domain.entities.models import MarketBar, StrategyPerformance
    from packages.domain.enums.common import Timeframe as _TF

    # ── Fetch instrument ──
    inst_result = await db.execute(select(Instrument).where(Instrument.id == instrument_id))
    instrument = inst_result.scalar_one_or_none()
    if not instrument:
        raise ValueError("Instrument not found")

    symbol = instrument.symbol

    # ── Memory: resolve pending outcomes from past runs ──
    memory = DecisionMemoryLog()
    try:
        resolve_pending_outcomes(memory, symbol=symbol)
    except Exception as e:
        logger.warning(f"[{symbol}] Outcome resolution failed (non-fatal): {e}")

    # ── Memory: get past context for prompt injection ──
    past_context = memory.get_past_context(symbol)
    if past_context:
        logger.info(f"[{symbol}] Injecting {len(past_context)} chars of past context")

    # ── Get current price ──
    current_price = None
    price_is_live = False
    try:
        import yfinance as yf
        fast_info = yf.Ticker(symbol).fast_info
        live_price = fast_info.get("lastPrice") if hasattr(fast_info, "get") else getattr(fast_info, "last_price", None)
        if live_price:
            current_price = float(live_price)
            price_is_live = True
    except Exception as e:
        logger.warning(f"Live price fetch failed for {symbol}, falling back to stored bar: {e}")

    if current_price is None:
        price_result = await db.execute(
            select(MarketBar)
            .where(MarketBar.instrument_id == instrument_id, MarketBar.timeframe == _TF.DAILY)
            .order_by(MarketBar.ts_open.desc())
            .limit(1)
        )
        latest_bar = price_result.scalar_one_or_none()
        current_price = float(latest_bar.close) if latest_bar else None

    # ── Step 1: Sentiment Analysis ──
    logger.info(f"[{symbol}] Running sentiment analysis...")
    try:
        sentiment_report, sentiment_markdown = await analyze_sentiment(db, instrument_id)
    except Exception as e:
        logger.warning(f"[{symbol}] Sentiment analysis failed: {e}")
        sentiment_report = None
        sentiment_markdown = "Sentiment analysis unavailable."

    # ── Step 2: Technical Strategies ──
    logger.info(f"[{symbol}] Running technical strategies...")
    technical_signals = await generate_signals_for_instrument(db, instrument_id)
    lean, counted = _deterministic_lean(technical_signals)

    # Pull backtest win rates
    strategy_breakdown = []
    for s in technical_signals:
        if s.get("error"):
            continue
        strat_name = s.get("strategy")
        win_rate = None
        if strat_name:
            try:
                perf_result = await db.execute(
                    select(StrategyPerformance).where(
                        StrategyPerformance.strategy_name == strat_name,
                        StrategyPerformance.instrument_id == instrument_id,
                    )
                )
                perf = perf_result.scalar_one_or_none()
                if perf and perf.win_rate is not None:
                    win_rate = float(perf.win_rate)
            except Exception:
                pass
            if win_rate is None:
                try:
                    agg_result = await db.execute(
                        select(StrategyPerformance).where(
                            StrategyPerformance.strategy_name == strat_name,
                        )
                    )
                    all_perfs = agg_result.scalars().all()
                    valid = [float(p.win_rate) for p in all_perfs if p.win_rate is not None and p.total_trades and p.total_trades > 0]
                    if valid:
                        win_rate = sum(valid) / len(valid)
                except Exception:
                    pass

        strategy_breakdown.append({
            "strategy": strat_name,
            "state": s.get("state"),
            "confidence": s.get("confidence"),
            "win_rate": win_rate,
        })

    strategy_lines = "\n".join(
        f"- {b['strategy']}: {b['state']} (confidence {b['confidence']:.0%})"
        + (f" — historical win rate: {b['win_rate']:.0f}%" if b.get('win_rate') is not None else " — no backtest data yet")
        for b in strategy_breakdown
    ) or "No technical strategies produced a signal."

    # ── Step 3: Bull/Bear Debate ──
    logger.info(f"[{symbol}] Running bull/bear debate...")
    try:
        debate = await run_debate(db, instrument_id)
    except Exception as e:
        logger.warning(f"[{symbol}] Debate failed: {e}")
        debate = None

    # ── Step 4: Analyst consensus ──
    analyst_line = ""
    try:
        import yfinance as yf
        yf_info = yf.Ticker(symbol).info
        mean_target = yf_info.get("targetMeanPrice")
        high_target = yf_info.get("targetHighPrice")
        low_target = yf_info.get("targetLowPrice")
        rec = yf_info.get("recommendationKey")
        n_analysts = yf_info.get("numberOfAnalystOpinions")
        if mean_target and n_analysts:
            analyst_line = (
                f"WALL STREET ANALYST CONSENSUS ({n_analysts} analysts):\n"
                f"- Average price target: ${mean_target:.2f} "
                f"(range: ${low_target:.2f} - ${high_target:.2f})\n"
                f"- Consensus rating: {(rec or 'unknown').replace('_', ' ').upper()}\n\n"
            )
    except Exception as e:
        logger.warning(f"Could not fetch analyst consensus: {e}")

    # ── Build chief analyst evidence block ──
    price_source = "live quote" if price_is_live else "last stored daily close, may be stale"
    price_line = f"CURRENT PRICE: ${current_price:.2f} ({price_source})\n\n" if current_price else "CURRENT PRICE: unavailable\n\n"

    debate_section = ""
    if debate:
        debate_section = (
            f"DEBATE VERDICT (after {debate.rounds_completed} rounds):\n{debate.verdict}\n"
            f"Risk level: {debate.risk_level} — {debate.risk_reasoning}\n"
            f"Suggested entry: {debate.suggested_entry}\n"
            f"Stop-loss: {debate.suggested_stop_loss}\n"
            f"Take-profit: {debate.suggested_take_profit}\n\n"
        )

    sentiment_section = ""
    if sentiment_report:
        sentiment_section = f"SENTIMENT ANALYSIS:\n{sentiment_markdown}\n\n"

    past_context_section = ""
    if past_context:
        past_context_section = f"LESSONS FROM PAST DECISIONS:\n{past_context}\n\n"

    evidence_block = (
        price_line + analyst_line +
        f"TECHNICAL STRATEGIES ({counted} with signal, out of {len(technical_signals)}):\n"
        f"{strategy_lines}\n\n"
        f"{sentiment_section}"
        f"{debate_section}"
        f"{past_context_section}"
    )

    # ── Step 5: Chief Analyst — structured trade proposal ──
    logger.info(f"[{symbol}] Running chief analyst synthesis...")
    chief_system = (
        "You are the chief analyst synthesizing multiple inputs into ONE trade proposal. "
        "You are given: (1) technical strategies with confidence and backtest win rates, "
        "(2) a sentiment report with band/score/confidence, (3) a bull/bear debate verdict, "
        "(4) Wall Street analyst consensus. These inputs may disagree — that is normal.\n\n"
        "IMPORTANT:\n"
        "- Weigh strategies by historical win rate\n"
        "- Ground entry/stop/price levels in the CURRENT PRICE\n"
        "- Stop-loss must be below entry zone, take-profit above\n"
        "- Minimum 2:1 reward-to-risk ratio\n"
        "- Be specific with numbers, not vague ranges\n"
        "- For entry, prefer a REALISTIC plan over 'wait for a dip that may never come':\n"
        "  state a concrete entry level AND acknowledge how reachable it is. If price is\n"
        "  extended, suggest scaling in rather than waiting for a deep pullback."
    )

    chief_user = (
        f"Analyze {symbol} and produce a trade proposal.\n\n"
        f"{evidence_block}"
    )

    from packages.agents.schemas import TraderProposal, TraderAction
    client = OllamaClient()

    proposal = structured_chat(
        client, chief_system, chief_user,
        schema=TraderProposal,
        temperature=0.2,
    )

    if proposal is None:
        # Fallback to deterministic lean
        proposal = TraderProposal(
            action=TraderAction.BUY if lean > 0.3 else (TraderAction.SELL if lean < -0.3 else TraderAction.HOLD),
            reasoning=f"LLM unavailable. Deterministic lean: {lean:+.2f}. {debate.verdict[:200] if debate else ''}",
            entry_price=current_price,
            stop_loss=round(current_price * 0.95, 2) if current_price else None,
            position_sizing="2-3% of portfolio (conservative default)",
        )

    from packages.agents.schemas import render_trader_proposal
    proposal_markdown = render_trader_proposal(proposal)

    # ── Step 6: Risk Debate → Portfolio Manager ──
    logger.info(f"[{symbol}] Running risk debate...")
    bull_text = debate.bull_case if debate else "No debate available."
    bear_text = debate.bear_case if debate else "No debate available."

    try:
        pm_rendered, pm_decision = await run_risk_debate(
            symbol=symbol,
            trade_proposal=proposal_markdown,
            bull_case=bull_text,
            bear_case=bear_text,
            current_price=current_price,
        )
    except Exception as e:
        logger.warning(f"[{symbol}] Risk debate failed: {e}")
        pm_decision = PortfolioDecision(
            rating=PortfolioRating.HOLD,
            executive_summary=f"Risk debate failed: {e}",
            investment_thesis="Unable to complete risk analysis.",
        )
        pm_rendered = render_pm_decision(pm_decision)

    # ── Build final ConsolidatedSignal ──
    # Map PM rating to our signal states
    rating_to_state = {
        PortfolioRating.BUY: "ENTER_LONG",
        PortfolioRating.OVERWEIGHT: "ENTER_LONG",
        PortfolioRating.HOLD: "HOLD",
        PortfolioRating.UNDERWEIGHT: "REDUCE",
        PortfolioRating.SELL: "EXIT",
    }
    final_state = rating_to_state.get(pm_decision.rating, "HOLD")

    # Derive confidence from alignment
    alignment_score = 50.0
    if debate and debate.risk_level == "LOW":
        alignment_score += 15
    elif debate and debate.risk_level == "HIGH":
        alignment_score -= 15
    if sentiment_report:
        if sentiment_report.overall_band.value in ("Bullish", "Mildly Bullish") and final_state == "ENTER_LONG":
            alignment_score += 10
        elif sentiment_report.overall_band.value in ("Bearish", "Mildly Bearish") and final_state in ("EXIT", "REDUCE"):
            alignment_score += 10
        elif sentiment_report.overall_band.value in ("Bullish", "Mildly Bullish") and final_state in ("EXIT", "REDUCE"):
            alignment_score -= 10
    if counted > 0:
        alignment_score += min(20, counted * 3)
    alignment_score = max(0, min(100, alignment_score))

    # Extract entry/stop/target from proposal
    entry_str = f"${proposal.entry_price:.2f}" if proposal.entry_price else "See proposal"
    stop_str = f"${proposal.stop_loss:.2f}" if proposal.stop_loss else "See proposal"
    # Try to get take-profit from PM decision
    tp_str = f"${pm_decision.price_target:.2f}" if pm_decision.price_target else "See analysis"

    # ── Memory: store decision for future reflection ──
    try:
        memory.store_decision(
            symbol=symbol,
            trade_date=datetime.now().strftime("%Y-%m-%d"),
            final_state=final_state,
            confidence=alignment_score,
            summary=pm_decision.executive_summary,
            entry_zone=entry_str,
            stop_loss=stop_str,
            take_profit=tp_str,
            risk_level=debate.risk_level if debate else "MEDIUM",
            strategy_breakdown=strategy_breakdown,
            sentiment_band=sentiment_report.overall_band.value if sentiment_report else None,
            sentiment_score=sentiment_report.overall_score if sentiment_report else None,
        )
    except Exception as e:
        logger.warning(f"[{symbol}] Failed to store decision in memory: {e}")

    # ── Step 7: Realistic entry plan + portfolio-aware action (deterministic) ──
    horizon_days = _horizon_days_from(pm_decision)
    expires = _prob.till_date(horizon_days)

    annual_vol = 0.30
    try:
        closes = await _recent_closes(db, instrument_id, limit=90)
        if len(closes) >= 2:
            annual_vol = _prob.annualized_volatility(closes)
    except Exception as e:
        logger.warning(f"[{symbol}] vol estimate failed, defaulting 0.30: {e}")

    dream_entry = proposal.entry_price if proposal.entry_price else (
        round(current_price * 0.97, 2) if current_price else None
    )
    entry_probability = None
    entry_plan = None
    if current_price and dream_entry and final_state in ("ENTER_LONG", "HOLD", "WATCH"):
        try:
            plan = _prob.realistic_entry_plan(
                current_price, dream_entry, horizon_days, annual_vol, direction="long"
            )
            entry_probability = plan.prob_reach_entry
            entry_plan = {
                "current": plan.current,
                "dream_entry": plan.dream_entry,
                "prob_reach_entry": round(plan.prob_reach_entry, 4),
                "likely_to_miss": plan.likely_to_miss,
                "horizon_days": plan.horizon_days,
                "expires": plan.expires.isoformat(),
                "expected_entry": plan.expected_entry,
                "ladders": [
                    {"trigger": r.trigger, "fraction": r.fraction, "note": r.note}
                    for r in plan.ladders
                ],
                "plain_language": plan.plain_language,
            }
        except Exception as e:
            logger.warning(f"[{symbol}] entry plan failed: {e}")

    portfolio_action = None
    try:
        pf_value = portfolio_value or ((position_qty * (avg_cost or current_price or 0.0)) or 100_000.0)
        ctx = _Ctx(
            current_price=current_price or 0.0,
            portfolio_value=pf_value,
            quantity=position_qty,
            avg_cost=avg_cost,
            target_weight=target_weight,
        )
        dec = _recommend(final_state, ctx, stop_price=stop_price)
        portfolio_action = {
            "action": dec.action.value,
            "trade_shares": dec.trade_shares,
            "trade_value": dec.trade_value,
            "trade_pct_of_position": dec.trade_pct_of_position,
            "new_weight": dec.new_weight,
            "pnl_pct": dec.pnl_pct,
            "rationale": dec.rationale,
        }
    except Exception as e:
        logger.warning(f"[{symbol}] portfolio action failed: {e}")

    return ConsolidatedSignal(
        symbol=symbol,
        final_state=FinalState(final_state),
        final_confidence=alignment_score,
        summary=pm_decision.executive_summary,
        entry_zone=entry_str,
        stop_loss=stop_str,
        take_profit=tp_str,
        risk_level=RiskLevel(debate.risk_level) if debate else RiskLevel.MEDIUM,
        risk_reasoning=debate.risk_reasoning if debate else "Risk debate unavailable.",
        strategy_breakdown=strategy_breakdown,
        debate_included=debate is not None,
        llm_used=True,
        current_price=current_price,
        horizon_days=horizon_days,
        till_date=expires.isoformat(),
        entry_probability=entry_probability,
        entry_plan=entry_plan,
        portfolio_action=portfolio_action,
    )
