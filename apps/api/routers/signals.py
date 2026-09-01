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
