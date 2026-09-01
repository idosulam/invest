"""Allowlisted read-only tools for LLM reasoning — PRD Section 7.

These tools retrieve stored data for the evidence compiler.
No write access, no shell, no SQL, no network — strictly read-only.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from packages.domain.entities.models import (
    Instrument, MarketBar, Signal, StrategyVersion, FundamentalFact,
    BacktestRun, EvidenceItem, DataSnapshot,
)
from packages.domain.enums.common import Timeframe


# ── Tool: Get instrument info ───────────────────────────────

async def get_instrument_info(
    db: AsyncSession,
    instrument_id: uuid.UUID,
) -> Optional[dict]:
    """Retrieve instrument metadata."""
    result = await db.execute(select(Instrument).where(Instrument.id == instrument_id))
    inst = result.scalar_one_or_none()
    if not inst:
        return None
    return {
        "id": str(inst.id),
        "symbol": inst.symbol,
        "name": inst.name,
        "type": inst.type.value,
        "exchange": inst.exchange,
        "sector": inst.sector,
        "industry": inst.industry,
        "currency": inst.currency,
        "status": inst.status.value,
    }


# ── Tool: Get recent bars ───────────────────────────────────

async def get_recent_bars(
    db: AsyncSession,
    instrument_id: uuid.UUID,
    timeframe: str = "1D",
    limit: int = 30,
) -> list[dict]:
    """Retrieve recent OHLCV bars."""
    tf = Timeframe(timeframe)
    result = await db.execute(
        select(MarketBar)
        .where(MarketBar.instrument_id == instrument_id, MarketBar.timeframe == tf)
        .order_by(desc(MarketBar.ts_open))
        .limit(limit)
    )
    bars = result.scalars().all()
    return [
        {
            "date": b.ts_open.strftime("%Y-%m-%d"),
            "open": float(b.open),
            "high": float(b.high),
            "low": float(b.low),
            "close": float(b.close),
            "volume": float(b.volume),
        }
        for b in reversed(bars)
    ]


# ── Tool: Get signals for instrument ────────────────────────

async def get_instrument_signals(
    db: AsyncSession,
    instrument_id: uuid.UUID,
    limit: int = 10,
) -> list[dict]:
    """Retrieve recent signals for an instrument."""
    result = await db.execute(
        select(Signal)
        .where(Signal.instrument_id == instrument_id)
        .order_by(desc(Signal.created_at))
        .limit(limit)
    )
    signals = result.scalars().all()

    items = []
    for s in signals:
        strat = (await db.execute(
            select(StrategyVersion).where(StrategyVersion.id == s.strategy_version_id)
        )).scalar_one_or_none()

        items.append({
            "id": str(s.id),
            "strategy": strat.name if strat else "unknown",
            "horizon": s.horizon.value,
            "state": s.state.value,
            "confidence": float(s.confidence),
            "quality_gate": s.quality_gate.value,
            "entry_zone": {
                "low": float(s.entry_zone_low) if s.entry_zone_low else None,
                "high": float(s.entry_zone_high) if s.entry_zone_high else None,
            },
            "invalidation": {
                "rule": s.invalidation_rule,
                "level": float(s.invalidation_level) if s.invalidation_level else None,
            },
            "reason_codes": s.reason_codes or [],
            "limitations": s.limitations or [],
            "as_of": s.as_of.strftime("%Y-%m-%d %H:%M"),
        })
    return items


# ── Tool: Get fundamentals ──────────────────────────────────

async def get_fundamentals(
    db: AsyncSession,
    instrument_id: uuid.UUID,
) -> list[dict]:
    """Retrieve fundamental data for an instrument."""
    result = await db.execute(
        select(FundamentalFact)
        .where(FundamentalFact.instrument_id == instrument_id)
        .order_by(desc(FundamentalFact.created_at))
    )
    facts = result.scalars().all()

    seen = set()
    items = []
    for f in facts:
        if f.taxonomy not in seen:
            items.append({
                "taxonomy": f.taxonomy,
                "period": f.period,
                "value": float(f.value),
                "unit": f.unit,
                "source": f.source,
            })
            seen.add(f.taxonomy)
    return items


# ── Tool: Get backtest summary ──────────────────────────────

async def get_backtest_summary(
    db: AsyncSession,
    strategy_name: Optional[str] = None,
    limit: int = 5,
) -> list[dict]:
    """Retrieve recent backtest results."""
    query = select(BacktestRun).order_by(desc(BacktestRun.created_at)).limit(limit)
    result = await db.execute(query)
    runs = result.scalars().all()

    return [
        {
            "id": str(r.id),
            "strategy": r.assumptions.get("strategy", "unknown"),
            "status": r.status.value,
            "metrics": r.metrics,
            "created_at": r.created_at.strftime("%Y-%m-%d"),
        }
        for r in runs
    ]


# ── Tool: Get strategy card ─────────────────────────────────

async def get_strategy_card(
    db: AsyncSession,
    strategy_version_id: uuid.UUID,
) -> Optional[dict]:
    """Retrieve strategy version details."""
    result = await db.execute(
        select(StrategyVersion).where(StrategyVersion.id == strategy_version_id)
    )
    sv = result.scalar_one_or_none()
    if not sv:
        return None
    return {
        "name": sv.name,
        "horizon": sv.horizon.value,
        "config": sv.config,
        "status": sv.status,
    }


# ── Tool registry ───────────────────────────────────────────

ALLOWLISTED_TOOLS = {
    "get_instrument_info": get_instrument_info,
    "get_recent_bars": get_recent_bars,
    "get_instrument_signals": get_instrument_signals,
    "get_fundamentals": get_fundamentals,
    "get_backtest_summary": get_backtest_summary,
    "get_strategy_card": get_strategy_card,
}
