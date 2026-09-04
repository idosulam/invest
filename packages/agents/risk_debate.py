"""Risk debate — Aggressive / Conservative / Neutral analysts.

Inspired by TradingAgents' risk management team:
After the Trader proposes a trade, three risk analysts debate:
- Aggressive: pushes for larger positions, tighter stops, more risk
- Conservative: advocates for smaller positions, wider stops, less risk
- Neutral: balances both perspectives pragmatically

A Portfolio Manager judge synthesizes the debate into a final
risk-adjusted decision.
"""

import logging

from apps.api.llm.ollama_client import OllamaClient
from packages.agents.schemas import (
    PortfolioDecision,
    PortfolioRating,
    RiskDebateVerdict,
    RiskLevel,
    render_pm_decision,
)
from packages.agents.structured import structured_chat

logger = logging.getLogger(__name__)

DEFAULT_RISK_ROUNDS = 2


def _build_risk_prompt(
    speaker: str,
    system_persona: str,
    trade_proposal: str,
    debate_history: str,
    opponent_latest: str,
    evidence_block: str,
) -> str:
    """Build a prompt for one risk debator."""
    base_context = (
        f"A trader has made the following proposal based on analyst research:\n\n"
        f"TRADE PROPOSAL:\n{trade_proposal}\n\n"
        f"SUPPORTING EVIDENCE:\n{evidence_block}"
    )

    if not opponent_latest:
        return (
            f"{system_persona}\n\n{base_context}\n\n"
            f"Present your opening risk argument. 3-5 sentences."
        )

    return (
        f"{system_persona}\n\n{base_context}\n\n"
        f"DEBATE SO FAR:\n{debate_history}\n\n"
        f"OPPONENT'S LATEST ARGUMENT:\n{opponent_latest}\n\n"
        f"Counter the opponent's points while reinforcing your position. 3-5 sentences."
    )


AGGRESSIVE_SYSTEM = (
    "You are an Aggressive Risk Analyst. You believe in conviction sizing — "
    "when the evidence is strong, take meaningful positions. You argue for: "
    "larger position sizes, tighter stop-losses (to avoid giving back gains), "
    "and being willing to accept short-term volatility for long-term alpha. "
    "You think most traders are too timid and leave money on the table. "
    "Cite specific evidence from the trade proposal."
)

CONSERVATIVE_SYSTEM = (
    "You are a Conservative Risk Analyst. You believe capital preservation is "
    "paramount — you can always re-enter, but you can't recover from a big loss. "
    "You argue for: smaller position sizes, wider stop-losses (to avoid being "
    "stopped out by noise), and taking partial profits early. "
    "You think most traders are overconfident and underestimate tail risk. "
    "Cite specific evidence from the trade proposal."
)

NEUTRAL_SYSTEM = (
    "You are a Neutral Risk Analyst. You balance conviction with prudence. "
    "You evaluate both the aggressive and conservative positions on their merits "
    "and try to find the pragmatic middle ground. You focus on: position sizing "
    "that matches the confidence level, stop-losses that reflect actual support "
    "levels rather than arbitrary percentages, and risk/reward ratios. "
    "You don't automatically split the difference — sometimes one side is right."
)

RISK_JUDGE_SYSTEM = (
    "You are the Portfolio Manager making the final risk-adjusted decision. "
    "You've seen the trader's proposal and the debate between aggressive, "
    "conservative, and neutral risk analysts. Your job is to:\n"
    "1. Approve, modify, or reject the trade proposal\n"
    "2. Set the final risk level and position sizing\n"
    "3. Provide a clear investment thesis\n\n"
    "You produce a structured decision with a 5-tier rating:\n"
    "- Buy: strong conviction, full position\n"
    "- Overweight: moderate conviction, slightly above benchmark\n"
    "- Hold: balanced evidence, maintain current exposure\n"
    "- Underweight: caution warranted, reduce exposure\n"
    "- Sell: clear bearish case, exit or avoid\n"
)


def _build_evidence_block(
    symbol: str,
    trade_proposal: str,
    bull_case: str,
    bear_case: str,
    current_price: float | None = None,
) -> str:
    """Build the evidence block for the risk debate."""
    parts = [f"SYMBOL: {symbol}"]
    if current_price:
        parts.append(f"CURRENT PRICE: ${current_price:.2f}")
    parts.extend([
        f"\nTRADE PROPOSAL:\n{trade_proposal}",
        f"\nBULL CASE (from debate):\n{bull_case}",
        f"\nBEAR CASE (from debate):\n{bear_case}",
    ])
    return "\n".join(parts)


async def run_risk_debate(
    symbol: str,
    trade_proposal: str,
    bull_case: str,
    bear_case: str,
    current_price: float | None = None,
    num_rounds: int = DEFAULT_RISK_ROUNDS,
) -> tuple[str, PortfolioDecision]:
    """Run the risk debate and return the Portfolio Manager's final decision.

    Args:
        symbol: Stock symbol
        trade_proposal: The Trader's proposal text
        bull_case: Bull researcher's arguments
        bear_case: Bear researcher's arguments
        current_price: Current stock price
        num_rounds: Number of debate rounds

    Returns:
        Tuple of (rendered_decision_markdown, PortfolioDecision).
    """
    client = OllamaClient()
    evidence_block = _build_evidence_block(symbol, trade_proposal, bull_case, bear_case, current_price)

    # Multi-round risk debate
    agg_history = ""
    con_history = ""
    neu_history = ""
    agg_latest = ""
    con_latest = ""
    neu_latest = ""

    for round_num in range(num_rounds):
        # Aggressive argues
        agg_prompt = _build_risk_prompt(
            "Aggressive", AGGRESSIVE_SYSTEM, trade_proposal,
            agg_history, con_latest or neu_latest, evidence_block,
        )
        try:
            agg_response = client.chat(AGGRESSIVE_SYSTEM, agg_prompt, temperature=0.4)
        except RuntimeError as e:
            agg_response = f"(Aggressive analyst unavailable: {e})"

        agg_arg = f"[Round {round_num + 1}] Aggressive: {agg_response}"
        agg_latest = agg_response
        agg_history += ("\n" if agg_history else "") + agg_arg

        # Conservative argues
        con_prompt = _build_risk_prompt(
            "Conservative", CONSERVATIVE_SYSTEM, trade_proposal,
            con_history, agg_latest, evidence_block,
        )
        try:
            con_response = client.chat(CONSERVATIVE_SYSTEM, con_prompt, temperature=0.4)
        except RuntimeError as e:
            con_response = f"(Conservative analyst unavailable: {e})"

        con_arg = f"[Round {round_num + 1}] Conservative: {con_response}"
        con_latest = con_response
        con_history += ("\n" if con_history else "") + con_arg

        # Neutral argues
        neu_prompt = _build_risk_prompt(
            "Neutral", NEUTRAL_SYSTEM, trade_proposal,
            neu_history, agg_latest + "\n\n" + con_latest, evidence_block,
        )
        try:
            neu_response = client.chat(NEUTRAL_SYSTEM, neu_prompt, temperature=0.4)
        except RuntimeError as e:
            neu_response = f"(Neutral analyst unavailable: {e})"

        neu_arg = f"[Round {round_num + 1}] Neutral: {neu_response}"
        neu_latest = neu_response
        neu_history += ("\n" if neu_history else "") + neu_arg

    # Full debate transcript for the Portfolio Manager
    full_debate = (
        f"AGGRESSIVE CASE:\n{agg_history}\n\n"
        f"CONSERVATIVE CASE:\n{con_history}\n\n"
        f"NEUTRAL CASE:\n{neu_history}"
    )

    pm_system = (
        f"{RISK_JUDGE_SYSTEM}\n\n"
        f"Respond with a JSON object with these fields:\n"
        f'  "rating": one of ["Buy", "Overweight", "Hold", "Underweight", "Sell"]\n'
        f'  "executive_summary": string — concise action plan (2-4 sentences)\n'
        f'  "investment_thesis": string — detailed reasoning from the full pipeline\n'
        f'  "price_target": number or null — target price\n'
        f'  "time_horizon": string or null — holding period, e.g. "3-6 months"\n\n'
        f"Return ONLY the JSON object."
    )
    pm_user = f"{evidence_block}\n\n{full_debate}\n\nTRADER'S PROPOSAL:\n{trade_proposal}"

    decision = structured_chat(
        client, pm_system, pm_user,
        schema=PortfolioDecision,
        temperature=0.2,
        max_retries=3,
    )

    if decision is None:
        # Smarter fallback: try to extract decision from debate text
        rating = PortfolioRating.HOLD
        summary = "Risk debate completed but LLM synthesis unavailable. Defaulting to Hold."

        debate_lower = full_debate.lower()
        proposal_lower = trade_proposal.lower()

        # Count sentiment signals in the debate
        bullish = sum(1 for w in ["buy", "bullish", "strong", "conviction", "upside", "outperform"] if w in debate_lower)
        bearish = sum(1 for w in ["sell", "bearish", "weak", "risk", "downside", "underperform", "exit"] if w in debate_lower)

        # Check the original proposal action
        if "buy" in proposal_lower or "enter_long" in proposal_lower or "bullish" in proposal_lower:
            proposal_lean = 1
        elif "sell" in proposal_lower or "exit" in proposal_lower or "bearish" in proposal_lower:
            proposal_lean = -1
        else:
            proposal_lean = 0

        combined = (bullish - bearish) + proposal_lean
        if combined >= 3:
            rating = PortfolioRating.BUY
            summary = "Risk debate showed strong bullish consensus. LLM synthesis failed — this is a mechanical fallback."
        elif combined >= 1:
            rating = PortfolioRating.OVERWEIGHT
            summary = "Risk debate leaned bullish. LLM synthesis failed — this is a mechanical fallback."
        elif combined <= -3:
            rating = PortfolioRating.SELL
            summary = "Risk debate showed strong bearish consensus. LLM synthesis failed — this is a mechanical fallback."
        elif combined <= -1:
            rating = PortfolioRating.UNDERWEIGHT
            summary = "Risk debate leaned bearish. LLM synthesis failed — this is a mechanical fallback."

        decision = PortfolioDecision(
            rating=rating,
            executive_summary=summary,
            investment_thesis=f"Mechanical fallback based on debate sentiment analysis. Trade proposal: {trade_proposal[:300]}",
            price_target=None,
            time_horizon=None,
        )

    rendered = render_pm_decision(decision)
    return rendered, decision
