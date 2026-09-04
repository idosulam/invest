"""Structured output schemas for all agents.

Inspired by TradingAgents' approach: every decision-making agent produces
typed Pydantic output so downstream consumers never regex-parse prose.

The render helpers convert schemas back to the same markdown shape the
rest of the system already consumes, so display, memory, and saved reports
keep working unchanged.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Shared enums
# ---------------------------------------------------------------------------

_NULLISH_FLOAT = {"", "none", "n/a", "na", "null", "nil", "-", "tbd", "unknown"}


def _coerce_optional_float(value):
    if isinstance(value, str) and value.strip().lower() in _NULLISH_FLOAT:
        return None
    return value


class PortfolioRating(str, Enum):
    """5-tier rating used by the Research Manager and Portfolio Manager."""
    BUY = "Buy"
    OVERWEIGHT = "Overweight"
    HOLD = "Hold"
    UNDERWEIGHT = "Underweight"
    SELL = "Sell"


class TraderAction(str, Enum):
    """3-tier transaction direction used by the Trader."""
    BUY = "Buy"
    HOLD = "Hold"
    SELL = "Sell"


class SentimentBand(str, Enum):
    """Discrete sentiment direction."""
    BULLISH = "Bullish"
    MILDLY_BULLISH = "Mildly Bullish"
    NEUTRAL = "Neutral"
    MIXED = "Mixed"
    MILDLY_BEARISH = "Mildly Bearish"
    BEARISH = "Bearish"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class FinalState(str, Enum):
    ENTER_LONG = "ENTER_LONG"
    EXIT = "EXIT"
    REDUCE = "REDUCE"
    HOLD = "HOLD"
    WATCH = "WATCH"


# ---------------------------------------------------------------------------
# Bull / Bear Debate
# ---------------------------------------------------------------------------

class DebateArgument(BaseModel):
    """A single argument in the bull/bear debate."""
    speaker: str = Field(description="Who made this argument: 'Bull' or 'Bear'")
    argument: str = Field(description="The full argument text, 3-5 sentences, citing specific evidence.")


class JudgeVerdict(BaseModel):
    """Structured verdict from the debate judge."""
    verdict: str = Field(
        description="One or two sentences: what a reasonable investor should do and why."
    )
    risk_level: RiskLevel = Field(
        description="Qualitative risk assessment: LOW, MEDIUM, or HIGH."
    )
    risk_reasoning: str = Field(
        description="One or two sentences explaining the risk level."
    )
    suggested_entry: str = Field(
        description=(
            "Concrete entry guidance. If bullish: a price level or condition for entry. "
            "If bearish/neutral: what would need to change before this becomes attractive. "
            "Never say 'Not applicable'."
        )
    )
    suggested_stop_loss: str = Field(
        description=(
            "Concrete price level or condition that confirms the thesis is wrong. "
            "Never say 'Not applicable'."
        )
    )
    suggested_take_profit: str = Field(
        description=(
            "Concrete price level, percentage, or condition to realize gains. "
            "Never say 'Not applicable'."
        )
    )


class DebateResult(BaseModel):
    """Full result of a bull/bear debate cycle."""
    symbol: str
    bull_case: str
    bear_case: str
    rounds_completed: int = Field(default=1, description="How many debate rounds were completed.")
    verdict: str
    risk_level: str
    risk_reasoning: str
    suggested_entry: str
    suggested_stop_loss: str
    suggested_take_profit: str
    evidence_summary: dict = Field(default_factory=dict)

    @classmethod
    def from_judge(cls, symbol: str, bull_case: str, bear_case: str,
                   rounds: int, judge: JudgeVerdict, evidence: dict) -> "DebateResult":
        return cls(
            symbol=symbol,
            bull_case=bull_case,
            bear_case=bear_case,
            rounds_completed=rounds,
            verdict=judge.verdict,
            risk_level=judge.risk_level.value,
            risk_reasoning=judge.risk_reasoning,
            suggested_entry=judge.suggested_entry,
            suggested_stop_loss=judge.suggested_stop_loss,
            suggested_take_profit=judge.suggested_take_profit,
            evidence_summary=evidence,
        )


# ---------------------------------------------------------------------------
# Sentiment Analyst
# ---------------------------------------------------------------------------

class SentimentReport(BaseModel):
    """Structured sentiment report."""
    overall_band: SentimentBand = Field(
        description=(
            "Overall sentiment direction. Exactly one of: "
            "Bullish / Mildly Bullish / Neutral / Mixed / Mildly Bearish / Bearish."
        )
    )
    overall_score: float = Field(
        ge=0.0, le=10.0,
        description=(
            "Numeric sentiment intensity on a 0-10 scale. "
            "0 = maximally bearish, 5 = neutral, 10 = maximally bullish."
        )
    )
    confidence: Literal["low", "medium", "high"] = Field(
        description="Confidence based on data quality and sample size."
    )
    narrative: str = Field(
        description=(
            "Full sentiment report covering: source-by-source breakdown with specific evidence, "
            "cross-source divergences, dominant themes, catalysts and risks, "
            "and a markdown table summarising key signals."
        )
    )


def render_sentiment_report(report: SentimentReport) -> str:
    """Render to markdown for storage and agent prompts."""
    return "\n".join([
        f"**Overall Sentiment:** **{report.overall_band.value}** "
        f"(Score: {report.overall_score:.1f}/10)",
        f"**Confidence:** {report.confidence.capitalize()}",
        "",
        report.narrative,
    ])


# ---------------------------------------------------------------------------
# Research Manager (synthesis of debate)
# ---------------------------------------------------------------------------

class ResearchPlan(BaseModel):
    """Structured investment plan from the Research Manager."""
    recommendation: PortfolioRating = Field(
        description=(
            "The investment recommendation. Exactly one of Buy / Overweight / "
            "Hold / Underweight / Sell. Choose Hold when evidence is balanced."
        )
    )
    rationale: str = Field(
        description="Summary of key points from both sides, ending with which led to the recommendation."
    )
    strategic_actions: str = Field(
        description="Concrete steps for the trader, including position sizing guidance."
    )


def render_research_plan(plan: ResearchPlan) -> str:
    return "\n".join([
        f"**Recommendation**: {plan.recommendation.value}",
        "",
        f"**Rationale**: {plan.rationale}",
        "",
        f"**Strategic Actions**: {plan.strategic_actions}",
    ])


# ---------------------------------------------------------------------------
# Trader
# ---------------------------------------------------------------------------

class TraderProposal(BaseModel):
    """Concrete transaction proposal from the Trader."""
    action: TraderAction = Field(
        description="The transaction direction: Buy / Hold / Sell."
    )
    reasoning: str = Field(
        description="The case for this action, anchored in evidence. 2-4 sentences."
    )
    entry_price: float | None = Field(
        default=None,
        description="Entry price target in the instrument's quote currency.",
    )
    stop_loss: float | None = Field(
        default=None,
        description="Stop-loss price in the instrument's quote currency.",
    )
    position_sizing: str | None = Field(
        default=None,
        description="Sizing guidance, e.g. '5% of portfolio'.",
    )

    @field_validator("entry_price", "stop_loss", mode="before")
    @classmethod
    def _nullish_float_to_none(cls, v):
        return _coerce_optional_float(v)


def render_trader_proposal(proposal: TraderProposal) -> str:
    parts = [
        f"**Action**: {proposal.action.value}",
        "",
        f"**Reasoning**: {proposal.reasoning}",
    ]
    if proposal.entry_price is not None:
        parts.extend(["", f"**Entry Price**: {proposal.entry_price}"])
    if proposal.stop_loss is not None:
        parts.extend(["", f"**Stop Loss**: {proposal.stop_loss}"])
    if proposal.position_sizing:
        parts.extend(["", f"**Position Sizing**: {proposal.position_sizing}"])
    parts.extend([
        "",
        f"FINAL TRANSACTION PROPOSAL: **{proposal.action.value.upper()}**",
    ])
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Risk Debate
# ---------------------------------------------------------------------------

class RiskArgument(BaseModel):
    """A single argument from a risk debator."""
    speaker: str = Field(description="'Aggressive', 'Conservative', or 'Neutral'")
    argument: str = Field(description="The full risk argument, 3-5 sentences.")


class RiskDebateVerdict(BaseModel):
    """Structured verdict from the risk debate judge."""
    decision: str = Field(
        description="Final risk-adjusted decision: approve, modify, or reject the trade proposal."
    )
    risk_level: RiskLevel
    risk_reasoning: str = Field(description="Why this risk level was assigned.")
    position_adjustment: str | None = Field(
        default=None,
        description="Any adjustment to position sizing or entry/stop levels."
    )


# ---------------------------------------------------------------------------
# Portfolio Manager (final decision)
# ---------------------------------------------------------------------------

class PortfolioDecision(BaseModel):
    """Final structured decision from the Portfolio Manager."""
    rating: PortfolioRating = Field(
        description=(
            "Final position rating: Buy / Overweight / Hold / Underweight / Sell. "
            "Choose Hold when the case is balanced or conflicting."
        )
    )
    executive_summary: str = Field(
        description="Concise action plan: entry strategy, position sizing, risk levels, time horizon. 2-4 sentences."
    )
    investment_thesis: str = Field(
        description="Detailed reasoning anchored in specific evidence from the full pipeline."
    )
    price_target: float | None = Field(
        default=None,
        description="Target price in the instrument's quote currency."
    )
    time_horizon: str | None = Field(
        default=None,
        description="Recommended holding period, e.g. '3-6 months'."
    )

    @field_validator("price_target", mode="before")
    @classmethod
    def _nullish_float_to_none(cls, v):
        return _coerce_optional_float(v)


def render_pm_decision(decision: PortfolioDecision) -> str:
    parts = [
        f"**Rating**: {decision.rating.value}",
        "",
        f"**Executive Summary**: {decision.executive_summary}",
        "",
        f"**Investment Thesis**: {decision.investment_thesis}",
    ]
    if decision.price_target is not None:
        parts.extend(["", f"**Price Target**: {decision.price_target}"])
    if decision.time_horizon:
        parts.extend(["", f"**Time Horizon**: {decision.time_horizon}"])
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Chief Analyst (consolidated signal) — kept for backwards compat
# ---------------------------------------------------------------------------

class ConsolidatedSignal(BaseModel):
    """Final consolidated signal from the chief analyst."""
    symbol: str
    final_state: FinalState
    final_confidence: float = Field(
        ge=0.0, le=100.0,
        description="How aligned the evidence is (0-100), not a probability of profit."
    )
    summary: str = Field(description="2-3 sentences explaining the final call in plain language.")
    entry_zone: str = Field(description="Specific price zone to enter, grounded in current price.")
    stop_loss: str = Field(description="Concrete stop-loss price level.")
    take_profit: str = Field(description="Concrete take-profit price level.")
    risk_level: RiskLevel
    risk_reasoning: str = Field(description="One sentence explaining the risk level.")
    strategy_breakdown: list[dict] = Field(default_factory=list)
    debate_included: bool = True
    llm_used: bool = True
