"""Consolidated signal — combines all technical strategies plus the
Bull/Bear/Judge debate into a single final verdict per instrument.

Two layers:
1. A deterministic vote: each technical strategy's state is weighted
   by its own confidence, giving a rough mechanical lean (bullish /
   bearish / neutral) that doesn't depend on the LLM being available.
2. An LLM "Chief Analyst" pass that is shown the full breakdown (all
   7 strategies' verdicts + the bull/bear debate + risk level) and
   asked to produce ONE final recommendation. If the LLM is
   unreachable, we fall back to the deterministic vote alone so the
   user still gets an answer.

This is a synthesis of existing evidence, not a new independent
prediction — it should never claim more certainty than its inputs.
"""

import logging
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.llm.ollama_client import OllamaClient
from packages.agents.debate import run_debate
from packages.strategies.engine import generate_signals_for_instrument
from packages.domain.enums.common import SignalState
from packages.domain.entities.models import Instrument

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


@dataclass
class ConsolidatedSignal:
    symbol: str
    final_state: str
    final_confidence: float
    summary: str
    entry_zone: str
    stop_loss: str
    take_profit: str
    risk_level: str
    risk_reasoning: str
    strategy_breakdown: list[dict] = field(default_factory=list)
    debate_included: bool = True
    llm_used: bool = True


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


async def run_consolidated_analysis(db: AsyncSession, instrument_id) -> ConsolidatedSignal:
    technical_signals = await generate_signals_for_instrument(db, instrument_id)
    debate = await run_debate(db, instrument_id)

    # Fetch the current price explicitly — this must never be left for the
    # LLM to infer indirectly from strategy entry zones, since that's how
    # we previously ended up with take-profit targets sitting $1 away from
    # the actual price. Prefer a live quote over the last stored bar, since
    # stored bars can be a day or more stale.
    from sqlalchemy import select
    from packages.domain.entities.models import MarketBar
    from packages.domain.enums.common import Timeframe as _TF

    inst_result = await db.execute(select(Instrument).where(Instrument.id == instrument_id))
    instrument = inst_result.scalar_one_or_none()
    if not instrument:
        raise ValueError("Instrument not found")

    current_price = None
    price_is_live = False
    try:
        import yfinance as yf
        fast_info = yf.Ticker(instrument.symbol).fast_info
        live_price = fast_info.get("lastPrice") if hasattr(fast_info, "get") else getattr(fast_info, "last_price", None)
        if live_price:
            current_price = float(live_price)
            price_is_live = True
    except Exception as e:
        logger.warning(f"Live price fetch failed for {instrument.symbol}, falling back to stored bar: {e}")

    if current_price is None:
        price_result = await db.execute(
            select(MarketBar)
            .where(MarketBar.instrument_id == instrument_id, MarketBar.timeframe == _TF.DAILY)
            .order_by(MarketBar.ts_open.desc())
            .limit(1)
        )
        latest_bar = price_result.scalar_one_or_none()
        current_price = float(latest_bar.close) if latest_bar else None

    lean, counted = _deterministic_lean(technical_signals)

    # Pull backtest win rates for each strategy from strategy_performance
    from packages.domain.entities.models import StrategyPerformance

    strategy_breakdown = []
    for s in technical_signals:
        if s.get("error"):
            continue
        strat_name = s.get("strategy")
        win_rate = None
        # Try instrument-specific win rate first, then aggregate
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
            # Fallback: aggregate across all instruments
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

    # Build the evidence block for the Chief Analyst LLM pass.
    strategy_lines = "\n".join(
        f"- {b['strategy']}: {b['state']} (confidence {b['confidence']:.0%})"
        + (f" — historical win rate: {b['win_rate']:.0f}%" if b.get('win_rate') is not None else " — no backtest data yet")
        for b in strategy_breakdown
    ) or "No technical strategies produced a signal."

    price_source_note = "live quote" if price_is_live else "last stored daily close, may be stale"
    price_line = (
        f"CURRENT PRICE: ${current_price:.2f} ({price_source_note})\n\n" if current_price else
        "CURRENT PRICE: unavailable\n\n"
    )

    # Free analyst consensus data (Yahoo Finance) — target prices and rating
    # from the pool of analysts actually covering this stock.
    analyst_line = ""
    try:
        import yfinance as yf
        if instrument:
            yf_info = yf.Ticker(instrument.symbol).info
            mean_target = yf_info.get("targetMeanPrice")
            high_target = yf_info.get("targetHighPrice")
            low_target = yf_info.get("targetLowPrice")
            rec = yf_info.get("recommendationKey")
            n_analysts = yf_info.get("numberOfAnalystOpinions")
            if mean_target and n_analysts:
                analyst_line = (
                    f"WALL STREET ANALYST CONSENSUS ({n_analysts} analysts covering this stock):\n"
                    f"- Average price target: ${mean_target:.2f} "
                    f"(range: ${low_target:.2f} - ${high_target:.2f})\n"
                    f"- Consensus rating: {(rec or 'unknown').replace('_', ' ').upper()}\n\n"
                )
    except Exception as e:
        logger.warning(f"Could not fetch analyst consensus: {e}")

    evidence_block = (
        price_line +
        analyst_line +
        f"TECHNICAL STRATEGIES ({counted} with a signal, out of {len(technical_signals)} run):\n"
        f"{strategy_lines}\n\n"
        f"NEWS/CONGRESS-INFORMED DEBATE VERDICT:\n{debate.verdict}\n"
        f"Debate risk level: {debate.risk_level} — {debate.risk_reasoning}\n"
        f"Debate suggested entry: {debate.suggested_entry}\n"
        f"Debate suggested stop-loss: {debate.suggested_stop_loss}\n"
        f"Debate suggested take-profit: {debate.suggested_take_profit}\n"
    )

    system = (
        "You are the chief analyst synthesizing multiple inputs into ONE final "
        "recommendation for a retail investor. You are given: (1) a set of "
        "independent technical trading strategies, each with its own verdict, "
        "confidence, AND historical backtest win rate for this specific stock "
        "(or aggregate across all stocks if per-stock data isn't available), "
        "(2) a separate debate-based verdict informed by news and congressional "
        "trading activity, and (3) Wall Street analyst consensus data (average "
        "price target and rating from professional analysts covering the stock, "
        "when available). These inputs may disagree — that is normal and expected. "
        "IMPORTANT: Weigh strategies by their historical win rate — a strategy "
        "with a 65% win rate on this stock deserves more weight than one with "
        "40%. If a strategy has no backtest data yet, treat its opinion as "
        "unverified and weigh it cautiously. Do not force false consensus. "
        "IMPORTANT: your STOP_LOSS and TAKE_PROFIT "
        "numbers must be your own reasoned levels based on ALL the evidence "
        "together (current price, technical levels, and analyst target range) "
        "— do not simply copy a number from the debate section without "
        "checking it makes sense against the current price and analyst range "
        "given in the evidence. Respond in EXACTLY this format, nothing else:\n\n"
        "FINAL_STATE: <one of ENTER_LONG, EXIT, REDUCE, HOLD, WATCH>\n"
        "FINAL_CONFIDENCE: <a number 0-100 representing how aligned the "
        "evidence is, not a probability of profit>\n"
        "SUMMARY: <2-3 sentences explaining the final call in plain language, "
        "referencing where the technical strategies, the debate, and the "
        "analyst consensus agreed or disagreed>\n"
        "ENTRY_ZONE: <ALWAYS give concrete guidance, even if FINAL_STATE is not "
        "ENTER_LONG. If bullish: the specific price zone to buy at. If not "
        "bullish: the specific price level, pullback, or condition that would "
        "need to happen before entry becomes attractive. Never say Not applicable.>\n"
        "STOP_LOSS: <a concrete price level, meaningfully below the CURRENT "
        "PRICE given in the evidence (a real risk buffer, not a price within "
        "a dollar or two of the current price) — always give one>\n"
        "TAKE_PROFIT: <a concrete price level, meaningfully above the CURRENT "
        "PRICE for a bullish stance (or below it for a bearish stance) — this "
        "must represent a real, worthwhile move, not a trivial change of a "
        "few dollars or a fraction of a percent. Base it on a sensible "
        "reward-to-risk ratio relative to the stop-loss distance — always "
        "give one>\n"
        "RISK_LEVEL: <LOW, MEDIUM, or HIGH>\n"
        "RISK_REASONING: <one sentence>"
    )

    client = OllamaClient()
    llm_used = True
    try:
        response = client.chat(system, evidence_block, temperature=0.2)
        parsed = _parse_chief_response(response)
    except RuntimeError as e:
        logger.warning(f"Chief analyst LLM unavailable, falling back to deterministic vote: {e}")
        llm_used = False
        parsed = _fallback_from_lean(lean, debate)

    return ConsolidatedSignal(
        symbol=debate.symbol,
        final_state=parsed["final_state"],
        final_confidence=parsed["final_confidence"],
        summary=parsed["summary"],
        entry_zone=parsed["entry_zone"],
        stop_loss=parsed["stop_loss"],
        take_profit=parsed["take_profit"],
        risk_level=parsed["risk_level"],
        risk_reasoning=parsed["risk_reasoning"],
        strategy_breakdown=strategy_breakdown,
        debate_included=True,
        llm_used=llm_used,
    )


def _parse_chief_response(text: str) -> dict:
    fields = {
        "final_state": "HOLD", "final_confidence": 30.0, "summary": "",
        "entry_zone": "Not applicable", "stop_loss": "", "take_profit": "",
        "risk_level": "MEDIUM", "risk_reasoning": "",
    }
    key_map = {
        "FINAL_STATE": "final_state", "FINAL_CONFIDENCE": "final_confidence",
        "SUMMARY": "summary", "ENTRY_ZONE": "entry_zone", "STOP_LOSS": "stop_loss",
        "TAKE_PROFIT": "take_profit", "RISK_LEVEL": "risk_level",
        "RISK_REASONING": "risk_reasoning",
    }
    for line in text.splitlines():
        line = line.strip()
        for prefix, key in key_map.items():
            if line.upper().startswith(prefix + ":"):
                val = line.split(":", 1)[1].strip()
                fields[key] = val
                break

    valid_states = {"ENTER_LONG", "EXIT", "REDUCE", "HOLD", "WATCH"}
    if fields["final_state"].upper() not in valid_states:
        fields["final_state"] = "HOLD"
    else:
        fields["final_state"] = fields["final_state"].upper()

    try:
        fields["final_confidence"] = max(0.0, min(100.0, float(str(fields["final_confidence"]).replace("%", ""))))
    except (ValueError, TypeError):
        fields["final_confidence"] = 30.0

    if fields["risk_level"].upper() not in ("LOW", "MEDIUM", "HIGH"):
        fields["risk_level"] = "MEDIUM"
    else:
        fields["risk_level"] = fields["risk_level"].upper()

    if not fields["summary"]:
        fields["summary"] = text[:400]

    return fields


def _fallback_from_lean(lean: float, debate) -> dict:
    """Used only if the LLM is unreachable — a simple rule-based fallback."""
    if lean > 0.3:
        state = "ENTER_LONG"
    elif lean < -0.3:
        state = "EXIT"
    else:
        state = "HOLD"
    return {
        "final_state": state,
        "final_confidence": min(abs(lean) * 100, 100.0),
        "summary": (
            f"LLM unavailable — this is a mechanical vote across technical "
            f"strategies only (debate evidence not weighed in). Lean score: {lean:+.2f}."
        ),
        "entry_zone": "Not applicable — LLM unavailable for detailed guidance",
        "stop_loss": debate.suggested_stop_loss or "Not available",
        "take_profit": debate.suggested_take_profit or "Not available",
        "risk_level": "MEDIUM",
        "risk_reasoning": "Elevated uncertainty — LLM synthesis unavailable, falling back to raw vote.",
    }
