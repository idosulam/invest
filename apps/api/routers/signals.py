"""Signal endpoints — PRD Section 5.1 (Standard output contract).

List, get, and generate signals. Each signal includes trigger, entry zone,
stop/invalidation, target methodology, evidence, risks and backtest context.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.auth import get_current_user, require_analyst
from apps.api.database import get_db
from packages.domain.entities.models import Signal, Instrument, StrategyVersion, User
from packages.domain.enums.common import Horizon, SignalState, QualityGate
from packages.strategies.engine import generate_signals_for_instrument
from packages.strategies.registry.strategy_base import StrategyRegistry

# Import strategies to trigger registration
import packages.strategies.swing  # noqa: F401
import packages.strategies.long_term  # noqa: F401
import packages.strategies.intraday  # noqa: F401

router = APIRouter(prefix="/signals", tags=["signals"])


# ── Schemas ─────────────────────────────────────────────────

class SignalResponse(BaseModel):
    id: uuid.UUID
    instrument_id: uuid.UUID
    symbol: Optional[str] = None
    instrument_name: Optional[str] = None
    as_of: datetime
    horizon: str
    state: str
    entry_zone_low: Optional[float] = None
    entry_zone_high: Optional[float] = None
    invalidation_rule: Optional[str] = None
    invalidation_level: Optional[float] = None
    target_method: Optional[str] = None
    max_loss_pct: Optional[float] = None
    suggested_size_pct: Optional[float] = None
    confidence: float
    quality_gate: str
    strategy_name: Optional[str] = None
    strategy_version_id: uuid.UUID
    data_snapshot_id: uuid.UUID
    evidence_ids: Optional[list] = None
    reason_codes: Optional[list] = None
    limitations: Optional[list] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SignalListResponse(BaseModel):
    items: list[SignalResponse]
    total: int
    page: int
    page_size: int


class GenerateRequest(BaseModel):
    instrument_id: uuid.UUID
    strategy_names: Optional[list[str]] = None
    horizon: Optional[Horizon] = None


class GenerateResponse(BaseModel):
    instrument_id: uuid.UUID
    signals_generated: int
    signals: list[dict]


class StrategyCardResponse(BaseModel):
    name: str
    version: str
    horizon: str
    description: str
    tags: list[str]
    required_lookback: int


# ── Endpoints ───────────────────────────────────────────────

@router.get("", response_model=SignalListResponse)
async def list_signals(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    horizon: Optional[Horizon] = None,
    state: Optional[SignalState] = None,
    quality_gate: Optional[QualityGate] = None,
    instrument_id: Optional[uuid.UUID] = None,
    min_confidence: Optional[float] = Query(None, ge=0, le=1),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """List signals with filtering and pagination."""
    query = select(Signal)
    count_query = select(func.count()).select_from(Signal)

    if horizon:
        query = query.where(Signal.horizon == horizon)
        count_query = count_query.where(Signal.horizon == horizon)
    if state:
        query = query.where(Signal.state == state)
        count_query = count_query.where(Signal.state == state)
    if quality_gate:
        query = query.where(Signal.quality_gate == quality_gate)
        count_query = count_query.where(Signal.quality_gate == quality_gate)
    if instrument_id:
        query = query.where(Signal.instrument_id == instrument_id)
        count_query = count_query.where(Signal.instrument_id == instrument_id)
    if min_confidence is not None:
        query = query.where(Signal.confidence >= min_confidence)
        count_query = count_query.where(Signal.confidence >= min_confidence)

    total = (await db.execute(count_query)).scalar()
    offset = (page - 1) * page_size

    result = await db.execute(
        query.order_by(desc(Signal.created_at)).offset(offset).limit(page_size)
    )
    signals = result.scalars().all()

    # Enrich with instrument and strategy names
    items = []
    for sig in signals:
        inst_result = await db.execute(select(Instrument).where(Instrument.id == sig.instrument_id))
        inst = inst_result.scalar_one_or_none()

        strat_result = await db.execute(select(StrategyVersion).where(StrategyVersion.id == sig.strategy_version_id))
        strat = strat_result.scalar_one_or_none()

        items.append(SignalResponse(
            id=sig.id,
            instrument_id=sig.instrument_id,
            symbol=inst.symbol if inst else None,
            instrument_name=inst.name if inst else None,
            as_of=sig.as_of,
            horizon=sig.horizon.value,
            state=sig.state.value,
            entry_zone_low=float(sig.entry_zone_low) if sig.entry_zone_low else None,
            entry_zone_high=float(sig.entry_zone_high) if sig.entry_zone_high else None,
            invalidation_rule=sig.invalidation_rule,
            invalidation_level=float(sig.invalidation_level) if sig.invalidation_level else None,
            target_method=sig.target_method,
            max_loss_pct=float(sig.max_loss_pct) if sig.max_loss_pct else None,
            suggested_size_pct=float(sig.suggested_size_pct) if sig.suggested_size_pct else None,
            confidence=float(sig.confidence),
            quality_gate=sig.quality_gate.value,
            strategy_name=strat.name if strat else None,
            strategy_version_id=sig.strategy_version_id,
            data_snapshot_id=sig.data_snapshot_id,
            evidence_ids=sig.evidence_ids,
            reason_codes=sig.reason_codes,
            limitations=sig.limitations,
            created_at=sig.created_at,
        ))

    return SignalListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/strategies", response_model=list[StrategyCardResponse])
async def list_strategies(
    horizon: Optional[Horizon] = None,
    _user: User = Depends(get_current_user),
):
    """List all registered strategy cards."""
    if horizon:
        cards = StrategyRegistry.list_by_horizon(horizon)
    else:
        cards = StrategyRegistry.list_all()

    return [
        StrategyCardResponse(
            name=c.name,
            version=c.version,
            horizon=c.horizon.value,
            description=c.description,
            tags=c.tags,
            required_lookback=c.required_lookback,
        )
        for c in cards
    ]


@router.get("/{signal_id}", response_model=SignalResponse)
async def get_signal(
    signal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Get a single signal with full details."""
    result = await db.execute(select(Signal).where(Signal.id == signal_id))
    signal = result.scalar_one_or_none()
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")

    inst_result = await db.execute(select(Instrument).where(Instrument.id == signal.instrument_id))
    inst = inst_result.scalar_one_or_none()

    strat_result = await db.execute(select(StrategyVersion).where(StrategyVersion.id == signal.strategy_version_id))
    strat = strat_result.scalar_one_or_none()

    return SignalResponse(
        id=signal.id,
        instrument_id=signal.instrument_id,
        symbol=inst.symbol if inst else None,
        instrument_name=inst.name if inst else None,
        as_of=signal.as_of,
        horizon=signal.horizon.value,
        state=signal.state.value,
        entry_zone_low=float(signal.entry_zone_low) if signal.entry_zone_low else None,
        entry_zone_high=float(signal.entry_zone_high) if signal.entry_zone_high else None,
        invalidation_rule=signal.invalidation_rule,
        invalidation_level=float(signal.invalidation_level) if signal.invalidation_level else None,
        target_method=signal.target_method,
        max_loss_pct=float(signal.max_loss_pct) if signal.max_loss_pct else None,
        suggested_size_pct=float(signal.suggested_size_pct) if signal.suggested_size_pct else None,
        confidence=float(signal.confidence),
        quality_gate=signal.quality_gate.value,
        strategy_name=strat.name if strat else None,
        strategy_version_id=signal.strategy_version_id,
        data_snapshot_id=signal.data_snapshot_id,
        evidence_ids=signal.evidence_ids,
        reason_codes=signal.reason_codes,
        limitations=signal.limitations,
        created_at=signal.created_at,
    )


@router.post("/generate", response_model=GenerateResponse)
async def generate_signals(
    req: GenerateRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_analyst),
):
    """Generate signals for an instrument using registered strategies.

    Runs all (or specified) strategies through the risk gate and
    persists valid signals.
    """
    signals = await generate_signals_for_instrument(
        db=db,
        instrument_id=req.instrument_id,
        strategy_names=req.strategy_names,
        horizon=req.horizon,
    )

    return GenerateResponse(
        instrument_id=req.instrument_id,
        signals_generated=len(signals),
        signals=signals,
    )


# ── Bull/Bear/Judge debate ────────────────────────────────────

class DebateResponse(BaseModel):
    symbol: str
    bull_case: str
    bear_case: str
    rounds_completed: int = 1
    verdict: str
    risk_level: str
    risk_reasoning: str
    suggested_entry: str
    suggested_stop_loss: str
    suggested_take_profit: str
    evidence_summary: dict
    data_sources_used: list[str] = ["price history", "news sentiment", "congressional trading"]
    data_sources_not_used: list[str] = ["institutional 13F filings (not yet integrated)"]


@router.post("/debate/{instrument_id}", response_model=DebateResponse)
async def run_debate_endpoint(
    instrument_id: uuid.UUID,
    rounds: int = Query(2, ge=1, le=5, description="Number of debate rounds"),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Run the Bull/Bear/Judge agent debate for an instrument.

    Multi-round debate: bull and bear argue across N rounds, then a judge
    synthesizes the result. Uses price action, news, congressional trading,
    and sentiment data as evidence.
    """
    from packages.agents.debate import run_debate

    try:
        result = await run_debate(db, instrument_id, num_rounds=rounds)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return DebateResponse(
        symbol=result.symbol,
        bull_case=result.bull_case,
        bear_case=result.bear_case,
        rounds_completed=result.rounds_completed,
        verdict=result.verdict,
        risk_level=result.risk_level,
        risk_reasoning=result.risk_reasoning,
        suggested_entry=result.suggested_entry,
        suggested_stop_loss=result.suggested_stop_loss,
        suggested_take_profit=result.suggested_take_profit,
        evidence_summary=result.evidence_summary,
    )


# ── Sentiment Analysis ──────────────────────────────────────

class SentimentResponse(BaseModel):
    symbol: str
    overall_band: str
    overall_score: float
    confidence: str
    narrative: str
    rendered_markdown: str


@router.post("/sentiment/{instrument_id}", response_model=SentimentResponse)
async def run_sentiment_endpoint(
    instrument_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Run structured sentiment analysis for an instrument.

    Aggregates news sentiment, congressional trading, and price momentum
    into a single structured report with band, score, and confidence.
    """
    from packages.agents.sentiment import analyze_sentiment
    from packages.agents.schemas import render_sentiment_report

    try:
        report, rendered = await analyze_sentiment(db, instrument_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    # Get symbol for response
    from sqlalchemy import select as sa_select
    from packages.domain.entities.models import Instrument
    inst_result = await db.execute(sa_select(Instrument).where(Instrument.id == instrument_id))
    inst = inst_result.scalar_one_or_none()
    symbol = inst.symbol if inst else "?"

    return SentimentResponse(
        symbol=symbol,
        overall_band=report.overall_band.value,
        overall_score=report.overall_score,
        confidence=report.confidence,
        narrative=report.narrative,
        rendered_markdown=rendered,
    )


# ── Consolidated final verdict ──────────────────────────────

class ConsolidatedResponse(BaseModel):
    symbol: str
    final_state: str
    final_confidence: float
    summary: str
    entry_zone: str
    stop_loss: str
    take_profit: str
    risk_level: str
    risk_reasoning: str
    strategy_breakdown: list[dict]
    debate_included: bool = True
    llm_used: bool


@router.post("/consolidated/{instrument_id}", response_model=ConsolidatedResponse)
async def run_consolidated_endpoint(
    instrument_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """One final verdict combining all technical strategies + the news/congress
    debate, synthesized by an LLM 'chief analyst' pass. Falls back to a
    deterministic vote if the LLM is unreachable.
    """
    from packages.agents.consolidate import run_consolidated_analysis

    try:
        result = await run_consolidated_analysis(db, instrument_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return ConsolidatedResponse(
        symbol=result.symbol,
        final_state=result.final_state.value if hasattr(result.final_state, 'value') else result.final_state,
        final_confidence=result.final_confidence,
        summary=result.summary,
        entry_zone=result.entry_zone,
        stop_loss=result.stop_loss,
        take_profit=result.take_profit,
        risk_level=result.risk_level.value if hasattr(result.risk_level, 'value') else result.risk_level,
        risk_reasoning=result.risk_reasoning,
        strategy_breakdown=result.strategy_breakdown,
        debate_included=result.debate_included,
        llm_used=result.llm_used,
    )


# ── Decision Memory Log ────────────────────────────────────

class MemoryEntryResponse(BaseModel):
    date: str
    symbol: str
    state: str
    confidence: str
    pending: bool
    raw_return: Optional[str] = None
    alpha_return: Optional[str] = None
    holding_days: Optional[int] = None
    resolved: Optional[str] = None
    decision: str
    reflection: Optional[str] = None


class MemoryLogResponse(BaseModel):
    entries: list[MemoryEntryResponse]
    total: int
    pending_count: int
    resolved_count: int


class ResolveResponse(BaseModel):
    resolved: int
    entries: list[dict]


@router.get("/memory", response_model=MemoryLogResponse)
async def get_memory_log(
    symbol: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    _user: User = Depends(get_current_user),
):
    """Get the decision memory log.

    Returns all entries (pending and resolved), optionally filtered by symbol.
    Pending entries are decisions awaiting outcome resolution.
    Resolved entries include actual returns and reflections.
    """
    from packages.agents.memory import DecisionMemoryLog

    memory = DecisionMemoryLog()
    entries = memory.load_entries()

    if symbol:
        entries = [e for e in entries if e.get("symbol") == symbol.upper()]

    # Most recent first
    entries = list(reversed(entries[-limit:]))

    pending_count = sum(1 for e in entries if e.get("pending"))
    resolved_count = len(entries) - pending_count

    items = [
        MemoryEntryResponse(
            date=e.get("date", ""),
            symbol=e.get("symbol", ""),
            state=e.get("state", ""),
            confidence=e.get("confidence", ""),
            pending=e.get("pending", False),
            raw_return=e.get("raw_return"),
            alpha_return=e.get("alpha_return"),
            holding_days=e.get("holding_days"),
            resolved=e.get("resolved"),
            decision=e.get("decision", ""),
            reflection=e.get("reflection"),
        )
        for e in entries
    ]

    return MemoryLogResponse(
        entries=items,
        total=len(items),
        pending_count=pending_count,
        resolved_count=resolved_count,
    )


@router.post("/memory/resolve", response_model=ResolveResponse)
async def resolve_memory_outcomes(
    symbol: Optional[str] = None,
    holding_days: int = Query(5, ge=1, le=30),
    _user: User = Depends(require_analyst),
):
    """Resolve pending decision entries with actual market outcomes.

    Fetches price data after the holding period, calculates returns
    vs benchmark, and generates LLM reflections on what held/failed.
    """
    from packages.agents.memory import DecisionMemoryLog
    from packages.agents.resolver import resolve_pending_outcomes

    memory = DecisionMemoryLog()
    resolved = resolve_pending_outcomes(
        memory, symbol=symbol, holding_days=holding_days,
    )

    return ResolveResponse(
        resolved=len(resolved),
        entries=resolved,
    )
