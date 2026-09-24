"""TradingAgents Portfolio Manager — portfolio-aware final decision.

Mirrors TradingAgents' "portfolio-aware runs": the decision is scaled to YOUR
book (position, cost basis, weight vs target), not just an abstract signal. The
deterministic position math is PURE + unit-tested and reuses
`packages.portfolio.action_advisor` (no duplication). An LLM may narrate the
decision (see `run_portfolio_manager`) but cannot change the numbers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from packages.portfolio.action_advisor import Action, PositionContext, recommend

# Map our Action -> TradingAgents 5-tier PortfolioRating vocabulary.
ACTION_TO_RATING = {
    Action.INITIATE: "Buy",
    Action.ADD: "Overweight",
    Action.HOLD: "Hold",
    Action.TRIM: "Underweight",
    Action.EXIT: "Sell",
    Action.WATCH: "Hold",
    Action.AVOID: "Sell",
}


@dataclass
class PositionAssessment:
    has_position: bool
    pnl_pct: float
    weight: float
    target_weight: float
    over_target: bool


def assess_position(
    current_price: float,
    quantity: float,
    avg_cost: float,
    portfolio_value: float,
    target_weight: float = 0.05,
) -> PositionAssessment:
    """Snapshot of the holding relative to the book (pure)."""
    ctx = PositionContext(
        current_price=current_price,
        portfolio_value=portfolio_value,
        quantity=quantity,
        avg_cost=avg_cost,
        target_weight=target_weight,
    )
    return PositionAssessment(
        has_position=ctx.has_position,
        pnl_pct=ctx.pnl_pct,
        weight=ctx.weight,
        target_weight=target_weight,
        over_target=ctx.weight >= target_weight,
    )


def decide_for_book(
    signal_state: str,
    current_price: float,
    quantity: float,
    avg_cost: float,
    portfolio_value: float,
    target_weight: float = 0.05,
    stop_price: Optional[float] = None,
) -> dict:
    """Deterministic portfolio-aware action + rating + sizing + rationale (pure)."""
    ctx = PositionContext(
        current_price=current_price,
        portfolio_value=portfolio_value,
        quantity=quantity,
        avg_cost=avg_cost,
        target_weight=target_weight,
    )
    dec = recommend(signal_state, ctx, stop_price=stop_price)
    return {
        "rating": ACTION_TO_RATING.get(dec.action, "Hold"),
        "action": dec.action.value,
        "trade_shares": dec.trade_shares,
        "trade_value": dec.trade_value,
        "trade_pct_of_position": dec.trade_pct_of_position,
        "new_weight": dec.new_weight,
        "pnl_pct": dec.pnl_pct,
        "rationale": dec.rationale,
    }


def render_pm_action(decision: dict) -> str:
    """Render the portfolio-aware action as markdown (pure)."""
    parts = [
        f"**Rating**: {decision.get('rating')}",
        f"**Action**: {decision.get('action')}",
    ]
    if decision.get("trade_shares"):
        parts.append(
            f"**Trade**: {decision['trade_shares']:.2f} shares (${decision['trade_value']:,.0f})"
        )
    if decision.get("pnl_pct") is not None:
        parts.append(f"**Vs entry**: {decision['pnl_pct']:+.1%}")
    if decision.get("rationale"):
        parts.extend(["", str(decision["rationale"])])
    return "\n".join(parts)


async def run_portfolio_manager(
    symbol: str,
    trade_proposal: str,
    bull_case: str,
    bear_case: str,
    risk_verdict: str,
    current_price: float,
    quantity: float = 0.0,
    avg_cost: float = 0.0,
    portfolio_value: float = 0.0,
    target_weight: float = 0.05,
) -> str:
    """LLM Portfolio Manager synthesis, grounded by the deterministic action.

    Returns a markdown block. If the LLM is unavailable, falls back to the pure
    `decide_for_book` action so the output is always portfolio-aware and real.
    """
    deterministic = decide_for_book(
        _state_from_proposal(trade_proposal),
        current_price,
        quantity,
        avg_cost,
        portfolio_value or ((quantity * (avg_cost or current_price or 0.0)) or 100_000.0),
        target_weight,
    )
    action_block = render_pm_action(deterministic)

    try:
        from apps.api.llm.ollama_client import OllamaClient
        from packages.agents.schemas import PortfolioDecision, render_pm_decision
        from packages.agents.structured import structured_chat

        system = (
            "You are the Portfolio Manager making the final, portfolio-aware call. "
            "You are given a trade proposal, the bull/bear cases, a risk verdict, the "
            "current price, and the user's CURRENT POSITION (size, cost basis, weight). "
            "Scale the decision to the existing book: add if underweight and bullish, "
            "trim into strength if concentrated and up, hold if balanced. Ground every "
            "number in the current price and the position's cost basis."
        )
        user = (
            f"{symbol} @ ${current_price:.2f}\n\n"
            f"POSITION: qty={quantity} avg_cost={avg_cost} weight={deterministic['new_weight']:.1%} "
            f"(target {target_weight:.1%}), vs entry {deterministic['pnl_pct']:+.1%}\n\n"
            f"DETERMINISTIC ACTION (do not contradict these numbers):\n{action_block}\n\n"
            f"TRADE PROPOSAL:\n{trade_proposal}\n\nBULL:\n{bull_case}\n\nBEAR:\n{bear_case}\n\n"
            f"RISK VERDICT:\n{risk_verdict}"
        )
        client = OllamaClient()
        decision = structured_chat(client, system, user, schema=PortfolioDecision, temperature=0.2)
        if decision is not None:
            return render_pm_decision(decision) + "\n\n" + action_block
    except Exception:  # noqa: BLE001 - LLM optional
        pass

    return f"**Portfolio-aware decision (deterministic)**\n\n{action_block}"


def _state_from_proposal(trade_proposal: str) -> str:
    """Best-effort signal state from a proposal's text (for the deterministic fallback)."""
    text = (trade_proposal or "").upper()
    if "SELL" in text or "EXIT" in text:
        return "EXIT"
    if "REDUCE" in text or "TRIM" in text:
        return "REDUCE"
    if "BUY" in text or "ENTER_LONG" in text or "INITIATE" in text or "ADD" in text:
        return "ENTER_LONG"
    return "HOLD"
