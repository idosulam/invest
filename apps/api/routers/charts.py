"""Chart data endpoints — PRD Section 10 (Instrument workspace).

Serves OHLCV bars and computed indicator overlays for frontend charting.
All indicator calculations are deterministic and computed on-the-fly from
stored bars (no future data leakage).
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.auth import get_current_user
from apps.api.database import get_db
from packages.domain.entities.models import MarketBar, Instrument, User
from packages.domain.enums.common import Timeframe
from packages.features.indicators.canonical import (
    sma, ema, rsi, macd, bollinger_bands, atr, obv, adx, vwap_rolling,
)

router = APIRouter(prefix="/charts", tags=["charts"])


# ── Schemas ─────────────────────────────────────────────────

class BarPoint(BaseModel):
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    vwap: Optional[float] = None


class IndicatorLine(BaseModel):
    name: str
    values: list[Optional[float]]


class MACDData(BaseModel):
    macd: list[Optional[float]]
    signal: list[Optional[float]]
    histogram: list[Optional[float]]


class BollingerData(BaseModel):
    upper: list[Optional[float]]
    middle: list[Optional[float]]
    lower: list[Optional[float]]


class ChartResponse(BaseModel):
    instrument_id: uuid.UUID
    symbol: str
    timeframe: str
    bars: list[BarPoint]
    indicators: dict  # name -> list of values (aligned with bars)


# ── Available indicators ────────────────────────────────────

INDICATOR_REGISTRY = {
    "sma_20": lambda df: sma(df["close"], 20),
    "sma_50": lambda df: sma(df["close"], 50),
    "sma_200": lambda df: sma(df["close"], 200),
    "ema_12": lambda df: ema(df["close"], 12),
    "ema_26": lambda df: ema(df["close"], 26),
    "rsi_14": lambda df: rsi(df["close"], 14),
    "atr_14": lambda df: atr(df["high"], df["low"], df["close"], 14),
    "obv": lambda df: obv(df["close"], df["volume"]),
    "adx_14": lambda df: adx(df["high"], df["low"], df["close"], 14),
    "vwap_20": lambda df: vwap_rolling(df["high"], df["low"], df["close"], df["volume"], 20),
}


def _compute_indicator(name: str, df: pd.DataFrame) -> list[Optional[float]]:
    """Compute a single indicator, returning values aligned with bars."""
    if name == "macd":
        result = macd(df["close"])
        return {
            "macd": _to_list(result.macd),
            "signal": _to_list(result.signal),
            "histogram": _to_list(result.histogram),
        }
    elif name == "bollinger":
        result = bollinger_bands(df["close"])
        return {
            "upper": _to_list(result.upper),
            "middle": _to_list(result.middle),
            "lower": _to_list(result.lower),
        }
    elif name in INDICATOR_REGISTRY:
        series = INDICATOR_REGISTRY[name](df)
        return _to_list(series)
    else:
        raise ValueError(f"Unknown indicator: {name}")


def _to_list(series: pd.Series) -> list[Optional[float]]:
    """Convert pandas Series to list, replacing NaN with None."""
    return [None if pd.isna(v) else round(float(v), 6) for v in series]


# ── Endpoints ───────────────────────────────────────────────

@router.get("/indicators", response_model=list[str])
async def list_indicators():
    """List all available indicator names."""
    return sorted(list(INDICATOR_REGISTRY.keys()) + ["macd", "bollinger"])


@router.get("/{instrument_id}", response_model=ChartResponse)
async def get_chart_data(
    instrument_id: uuid.UUID,
    timeframe: Timeframe = Query(Timeframe.DAILY),
    start: Optional[datetime] = Query(None, description="Start date (UTC)"),
    end: Optional[datetime] = Query(None, description="End date (UTC)"),
    indicators: Optional[str] = Query(
        None,
        description="Comma-separated indicator names, e.g. 'sma_20,sma_50,rsi_14,macd'",
    ),
    limit: int = Query(500, ge=10, le=5000, description="Max bars to return"),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Get OHLCV bars with optional indicator overlays for charting.

    Returns bars in chronological order with any requested indicators
    computed and aligned to the same timestamps.
    """
    # Validate instrument
    inst_result = await db.execute(select(Instrument).where(Instrument.id == instrument_id))
    instrument = inst_result.scalar_one_or_none()
    if not instrument:
        raise HTTPException(status_code=404, detail="Instrument not found")

    # Build query
    query = (
        select(MarketBar)
        .where(MarketBar.instrument_id == instrument_id)
        .where(MarketBar.timeframe == timeframe)
        .order_by(MarketBar.ts_open)
    )
    if start:
        query = query.where(MarketBar.ts_open >= start)
    if end:
        query = query.where(MarketBar.ts_open <= end)
    query = query.limit(limit)

    result = await db.execute(query)
    bars = result.scalars().all()

    if not bars:
        return ChartResponse(
            instrument_id=instrument_id,
            symbol=instrument.symbol,
            timeframe=timeframe.value,
            bars=[],
            indicators={},
        )

    # Build DataFrame for indicator computation
    df = pd.DataFrame([
        {
            "open": float(b.open),
            "high": float(b.high),
            "low": float(b.low),
            "close": float(b.close),
            "volume": float(b.volume),
        }
        for b in bars
    ])

    # Build bar points
    bar_points = [
        BarPoint(
            ts=b.ts_open,
            open=float(b.open),
            high=float(b.high),
            low=float(b.low),
            close=float(b.close),
            volume=float(b.volume),
            vwap=float(b.vwap) if b.vwap else None,
        )
        for b in bars
    ]

    # Compute requested indicators
    computed = {}
    if indicators:
        requested = [name.strip() for name in indicators.split(",")]
        for name in requested:
            try:
                computed[name] = _compute_indicator(name, df)
            except ValueError:
                pass  # Skip unknown indicators silently

    return ChartResponse(
        instrument_id=instrument_id,
        symbol=instrument.symbol,
        timeframe=timeframe.value,
        bars=bar_points,
        indicators=computed,
    )
