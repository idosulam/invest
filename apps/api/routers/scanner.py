"""Scanner endpoint — PRD Section 1.3 (Run a scanner).

Filters instruments by technical and fundamental criteria.
Computes indicators on-the-fly and returns sortable results.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.auth import get_current_user
from apps.api.database import get_db
from packages.domain.entities.models import (
    MarketBar, Instrument, FundamentalFact, User,
)
from packages.domain.enums.common import InstrumentType, InstrumentStatus, Timeframe
from packages.features.indicators.canonical import rsi, sma, ema, atr, bollinger_bands, adx

router = APIRouter(prefix="/scanner", tags=["scanner"])


# ── Schemas ─────────────────────────────────────────────────

class ScanResult(BaseModel):
    instrument_id: uuid.UUID
    symbol: str
    name: str
    type: str
    exchange: Optional[str]
    sector: Optional[str]
    # Price data
    last_price: Optional[float] = None
    change_pct: Optional[float] = None
    volume_avg_20d: Optional[float] = None
    # Indicator values
    rsi_14: Optional[float] = None
    sma_20: Optional[float] = None
    sma_50: Optional[float] = None
    sma_200: Optional[float] = None
    atr_14: Optional[float] = None
    adx_14: Optional[float] = None
    bb_pct_b: Optional[float] = None
    # Trend signals
    above_sma_200: Optional[bool] = None
    sma_20_above_50: Optional[bool] = None
    # Fundamentals
    pe_ratio: Optional[float] = None
    market_cap: Optional[float] = None


class ScanResponse(BaseModel):
    results: list[ScanResult]
    total: int
    scan_time_ms: float


# ── Scan filters ────────────────────────────────────────────

class ScanFilters(BaseModel):
    # Technical
    min_rsi: Optional[float] = None
    max_rsi: Optional[float] = None
    above_sma_200: Optional[bool] = None
    sma_20_above_50: Optional[bool] = None
    min_adx: Optional[float] = None
    bb_oversold: Optional[bool] = None  # pct_b < 0.2
    bb_overbought: Optional[bool] = None  # pct_b > 0.8
    # Volume
    min_volume_avg: Optional[float] = None
    # Fundamental
    max_pe: Optional[float] = None
    min_pe: Optional[float] = None
    min_market_cap: Optional[float] = None
    # Meta
    instrument_type: Optional[InstrumentType] = None
    sector: Optional[str] = None


# ── Helpers ─────────────────────────────────────────────────

async def get_latest_bars(
    db: AsyncSession,
    instrument_ids: list[uuid.UUID],
    timeframe: Timeframe = Timeframe.DAILY,
    limit: int = 250,
) -> dict[uuid.UUID, pd.DataFrame]:
    """Fetch latest bars for a set of instruments, returned as DataFrames."""
    if not instrument_ids:
        return {}

    result = await db.execute(
        select(MarketBar)
        .where(
            MarketBar.instrument_id.in_(instrument_ids),
            MarketBar.timeframe == timeframe,
        )
        .order_by(MarketBar.instrument_id, MarketBar.ts_open.desc())
        .limit(limit * len(instrument_ids))
    )
    bars = result.scalars().all()

    # Group by instrument, keep most recent `limit` bars each
    grouped: dict[uuid.UUID, list] = {}
    for bar in bars:
        iid = bar.instrument_id
        if iid not in grouped:
            grouped[iid] = []
        if len(grouped[iid]) < limit:
            grouped[iid].append(bar)

    # Convert to DataFrames (chronological order)
    dfs = {}
    for iid, bar_list in grouped.items():
        sorted_bars = sorted(bar_list, key=lambda b: b.ts_open)
        dfs[iid] = pd.DataFrame([
            {
                "open": float(b.open),
                "high": float(b.high),
                "low": float(b.low),
                "close": float(b.close),
                "volume": float(b.volume),
            }
            for b in sorted_bars
        ])

    return dfs


def compute_scan_indicators(df: pd.DataFrame) -> dict:
    """Compute indicators needed for scan filters."""
    if len(df) < 20:
        return {}

    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]

    result = {}

    # RSI
    if len(df) >= 15:
        rsi_val = rsi(close, 14)
        result["rsi_14"] = round(float(rsi_val.iloc[-1]), 2) if not pd.isna(rsi_val.iloc[-1]) else None

    # SMAs
    if len(df) >= 20:
        sma20 = sma(close, 20)
        result["sma_20"] = round(float(sma20.iloc[-1]), 2) if not pd.isna(sma20.iloc[-1]) else None
    if len(df) >= 50:
        sma50 = sma(close, 50)
        result["sma_50"] = round(float(sma50.iloc[-1]), 2) if not pd.isna(sma50.iloc[-1]) else None
    if len(df) >= 200:
        sma200 = sma(close, 200)
        result["sma_200"] = round(float(sma200.iloc[-1]), 2) if not pd.isna(sma200.iloc[-1]) else None

    # ATR
    if len(df) >= 15:
        atr_val = atr(high, low, close, 14)
        result["atr_14"] = round(float(atr_val.iloc[-1]), 2) if not pd.isna(atr_val.iloc[-1]) else None

    # ADX
    if len(df) >= 28:
        adx_val = adx(high, low, close, 14)
        result["adx_14"] = round(float(adx_val.iloc[-1]), 2) if not pd.isna(adx_val.iloc[-1]) else None

    # Bollinger %B
    if len(df) >= 20:
        bb = bollinger_bands(close, 20)
        result["bb_pct_b"] = round(float(bb.pct_b.iloc[-1]), 4) if not pd.isna(bb.pct_b.iloc[-1]) else None

    # Price data
    result["last_price"] = round(float(close.iloc[-1]), 2)
    if len(df) >= 2:
        prev = float(close.iloc[-2])
        curr = float(close.iloc[-1])
        result["change_pct"] = round(((curr - prev) / prev) * 100, 2) if prev != 0 else None

    # 20-day avg volume
    if len(df) >= 20:
        result["volume_avg_20d"] = round(float(volume.tail(20).mean()), 0)

    # Trend signals
    if result.get("sma_20") and result.get("sma_200"):
        result["above_sma_200"] = result["last_price"] > result["sma_200"]
    if result.get("sma_20") and result.get("sma_50"):
        result["sma_20_above_50"] = result["sma_20"] > result["sma_50"]

    return result


# ── Endpoint ────────────────────────────────────────────────

@router.post("/run", response_model=ScanResponse)
async def run_scan(
    filters: ScanFilters,
    sort_by: str = Query("symbol", description="Sort field"),
    sort_dir: str = Query("asc", regex="^(asc|desc)$"),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Run a scanner with technical and fundamental filters.

    Computes indicators on-the-fly for all matching instruments.
    """
    import time
    start_time = time.time()

    # 1. Build instrument query
    query = select(Instrument).where(Instrument.status == InstrumentStatus.ACTIVE)

    if filters.instrument_type:
        query = query.where(Instrument.type == filters.instrument_type)
    if filters.sector:
        query = query.where(Instrument.sector.ilike(f"%{filters.sector}%"))

    result = await db.execute(query)
    instruments = result.scalars().all()

    if not instruments:
        return ScanResponse(results=[], total=0, scan_time_ms=0)

    # 2. Fetch bars for all instruments
    inst_ids = [i.id for i in instruments]
    bar_dfs = await get_latest_bars(db, inst_ids, Timeframe.DAILY, 250)

    # 3. Fetch fundamental data if needed
    pe_data: dict[uuid.UUID, float] = {}
    mcap_data: dict[uuid.UUID, float] = {}

    # Always fetch — used for display even when not filtering on them
    fund_result = await db.execute(
        select(FundamentalFact).where(
            FundamentalFact.instrument_id.in_(inst_ids),
            FundamentalFact.taxonomy.in_(["pe_ratio_ttm", "market_capitalization"]),
        )
    )
    for f in fund_result.scalars().all():
        if f.taxonomy == "pe_ratio_ttm":
            pe_data[f.instrument_id] = float(f.value)
        elif f.taxonomy == "market_capitalization":
            mcap_data[f.instrument_id] = float(f.value)

    # 4. Compute indicators and apply filters
    results: list[ScanResult] = []

    for inst in instruments:
        df = bar_dfs.get(inst.id)
        if df is None or len(df) < 20:
            continue

        indicators = compute_scan_indicators(df)
        if not indicators:
            continue

        # Apply technical filters
        if filters.min_rsi is not None and (indicators.get("rsi_14") is None or indicators["rsi_14"] < filters.min_rsi):
            continue
        if filters.max_rsi is not None and (indicators.get("rsi_14") is None or indicators["rsi_14"] > filters.max_rsi):
            continue
        if filters.above_sma_200 is not None and indicators.get("above_sma_200") != filters.above_sma_200:
            continue
        if filters.sma_20_above_50 is not None and indicators.get("sma_20_above_50") != filters.sma_20_above_50:
            continue
        if filters.min_adx is not None and (indicators.get("adx_14") is None or indicators["adx_14"] < filters.min_adx):
            continue
        if filters.bb_oversold and (indicators.get("bb_pct_b") is None or indicators["bb_pct_b"] >= 0.2):
            continue
        if filters.bb_overbought and (indicators.get("bb_pct_b") is None or indicators["bb_pct_b"] <= 0.8):
            continue
        if filters.min_volume_avg is not None and (indicators.get("volume_avg_20d") is None or indicators["volume_avg_20d"] < filters.min_volume_avg):
            continue

        # Apply fundamental filters
        pe = pe_data.get(inst.id)
        mcap = mcap_data.get(inst.id)
        if filters.max_pe is not None and (pe is None or pe > filters.max_pe):
            continue
        if filters.min_pe is not None and (pe is None or pe < filters.min_pe):
            continue
        if filters.min_market_cap is not None and (mcap is None or mcap < filters.min_market_cap):
            continue

        results.append(ScanResult(
            instrument_id=inst.id,
            symbol=inst.symbol,
            name=inst.name,
            type=inst.type.value,
            exchange=inst.exchange,
            sector=inst.sector,
            last_price=indicators.get("last_price"),
            change_pct=indicators.get("change_pct"),
            volume_avg_20d=indicators.get("volume_avg_20d"),
            rsi_14=indicators.get("rsi_14"),
            sma_20=indicators.get("sma_20"),
            sma_50=indicators.get("sma_50"),
            sma_200=indicators.get("sma_200"),
            atr_14=indicators.get("atr_14"),
            adx_14=indicators.get("adx_14"),
            bb_pct_b=indicators.get("bb_pct_b"),
            above_sma_200=indicators.get("above_sma_200"),
            sma_20_above_50=indicators.get("sma_20_above_50"),
            pe_ratio=pe_data.get(inst.id),
            market_cap=mcap_data.get(inst.id),
        ))

    # 5. Sort
    reverse = sort_dir == "desc"
    valid_sorts = [
        "symbol", "last_price", "change_pct", "volume_avg_20d",
        "rsi_14", "adx_14", "bb_pct_b", "pe_ratio", "market_cap",
    ]
    if sort_by in valid_sorts:
        results.sort(key=lambda r: getattr(r, sort_by) or 0, reverse=reverse)
    else:
        results.sort(key=lambda r: r.symbol or "")

    total = len(results)
    results = results[:limit]
    elapsed_ms = round((time.time() - start_time) * 1000, 1)

    return ScanResponse(results=results, total=total, scan_time_ms=elapsed_ms)


# ── Discovery: market-wide trending screener ────────────────

class DiscoveryResult(BaseModel):
    symbol: str
    name: Optional[str] = None
    last_price: Optional[float] = None
    change_pct: Optional[float] = None
    volume: Optional[float] = None
    market_cap: Optional[float] = None
    already_tracked: bool = False


class DiscoveryResponse(BaseModel):
    results: list[DiscoveryResult]
    screener: str
    total: int


DISCOVERY_SCREENERS = {
    "most_active": "most_actives",
    "day_gainers": "day_gainers",
    "day_losers": "day_losers",
    "growth_tech": "growth_technology_stocks",
    "small_cap_gainers": "small_cap_gainers",
}


@router.get("/discover", response_model=DiscoveryResponse)
async def discover_trending(
    screener: str = Query("most_active", description=f"One of: {', '.join(DISCOVERY_SCREENERS.keys())}"),
    limit: int = Query(25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Discover trending/active stocks from the broader market (not just tracked instruments).

    Pulls from Yahoo Finance's predefined screeners — no ticker list needed upfront.
    Cross-references against your tracked instruments so the UI can show which
    ones you already have and which are new candidates to add.
    """
    if screener not in DISCOVERY_SCREENERS:
        raise HTTPException(status_code=400, detail=f"Unknown screener. Choose from: {list(DISCOVERY_SCREENERS.keys())}")

    import yfinance as yf

    try:
        yahoo_screener_id = DISCOVERY_SCREENERS[screener]
        data = yf.screen(yahoo_screener_id, count=limit)
        quotes = data.get("quotes", [])
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch screener data: {e}")

    symbols_found = [q.get("symbol") for q in quotes if q.get("symbol")]

    # Cross-reference against tracked instruments
    tracked_symbols = set()
    if symbols_found:
        result = await db.execute(
            select(Instrument.symbol).where(Instrument.symbol.in_(symbols_found))
        )
        tracked_symbols = {row[0] for row in result.all()}

    results = []
    for q in quotes:
        symbol = q.get("symbol")
        if not symbol:
            continue
        results.append(DiscoveryResult(
            symbol=symbol,
            name=q.get("shortName") or q.get("longName"),
            last_price=q.get("regularMarketPrice"),
            change_pct=q.get("regularMarketChangePercent"),
            volume=q.get("regularMarketVolume"),
            market_cap=q.get("marketCap"),
            already_tracked=symbol in tracked_symbols,
        ))

    return DiscoveryResponse(results=results, screener=screener, total=len(results))
