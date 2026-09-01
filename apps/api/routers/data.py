"""Data ingestion API endpoints — Phase 2.

Provides endpoints for:
- Fetching data from Yahoo Finance
- Importing CSV/Parquet files
- Querying SEC EDGAR fundamentals
- Checking data quality
"""

import logging
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

# Auth deps will be overridden by the app
from apps.api.auth import get_current_user, require_analyst
try:
    from apps.api.database import get_db
except ImportError:
    pass
from packages.data.providers.yahoo_finance import YahooFinanceProvider
from packages.data.providers.sec_edgar import SECEdgarProvider
from packages.data.quality.validator import DataValidator
from packages.data.normalization.normalizer import DataNormalizer
from packages.domain.enums.common import Timeframe

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/data", tags=["data"])

# ── Providers ───────────────────────────────────────────────
yahoo = YahooFinanceProvider()
validator = DataValidator()
normalizer = DataNormalizer()


# ── Schemas ─────────────────────────────────────────────────

class FetchBarsRequest(BaseModel):
    symbols: list[str]
    timeframe: str = "1D"
    start: Optional[str] = None  # YYYY-MM-DD
    end: Optional[str] = None    # YYYY-MM-DD


class BarResponse(BaseModel):
    symbol: str
    timeframe: str
    ts_open: str
    open: float
    high: float
    low: float
    close: float
    volume: float


class FetchResult(BaseModel):
    symbol: str
    bars_fetched: int
    quality_status: str
    issues: list[str]


class FundamentalResponse(BaseModel):
    symbol: str
    taxonomy: str
    period: str
    value: float
    unit: str


class InstrumentLookupResponse(BaseModel):
    symbol: str
    name: str
    type: str
    exchange: Optional[str]
    sector: Optional[str]
    industry: Optional[str]
    country: Optional[str]


class HealthResponse(BaseModel):
    provider: str
    status: str
    error: Optional[str] = None


# ── Yahoo Finance endpoints ────────────────────────────────

@router.post("/fetch/bars", response_model=list[FetchResult])
async def fetch_bars(
    req: FetchBarsRequest,
    _user: Any = Depends(require_analyst),
):
    """Fetch OHLCV bars from Yahoo Finance and validate quality."""
    timeframe_map = {
        "1D": Timeframe.DAILY,
        "1H": Timeframe.HOURLY,
        "15m": Timeframe.MINUTE_15,
        "5m": Timeframe.MINUTE_5,
        "1m": Timeframe.MINUTE_1,
    }
    tf = timeframe_map.get(req.timeframe, Timeframe.DAILY)

    start = datetime.strptime(req.start, "%Y-%m-%d") if req.start else None
    end = datetime.strptime(req.end, "%Y-%m-%d") if req.end else None

    from packages.data.providers.base import BarsRequest
    bars_req = BarsRequest(symbols=req.symbols, timeframe=tf, start=start, end=end)

    results = []
    for symbol in req.symbols:
        # Fetch bars for this symbol
        symbol_req = BarsRequest(symbols=[symbol], timeframe=tf, start=start, end=end)
        bars = list(yahoo.bars(symbol_req))

        if not bars:
            results.append(FetchResult(
                symbol=symbol,
                bars_fetched=0,
                quality_status="NO_DATA",
                issues=["No data returned from provider"],
            ))
            continue

        # Normalize
        normalized = [normalizer.normalize_bar(b) for b in bars]

        # Validate
        validation = validator.validate_bars(normalized)

        results.append(FetchResult(
            symbol=symbol,
            bars_fetched=len(bars),
            quality_status=validation.status.value,
            issues=[i.description for i in validation.issues[:10]],  # Top 10 issues
        ))

    return results


@router.get("/lookup/{symbol}", response_model=InstrumentLookupResponse)
async def lookup_instrument(
    symbol: str,
    _user: Any = Depends(get_current_user),
):
    """Look up instrument metadata from Yahoo Finance."""
    info = yahoo.get_instrument_info(symbol)
    if not info:
        raise HTTPException(404, f"Instrument '{symbol}' not found")
    return InstrumentLookupResponse(
        symbol=info.symbol,
        name=info.name,
        type=info.type.value,
        exchange=info.exchange,
        sector=info.sector,
        industry=info.industry,
        country=info.country,
    )


@router.get("/fundamentals/{symbol}", response_model=list[FundamentalResponse])
async def get_fundamentals(
    symbol: str,
    _user: Any = Depends(get_current_user),
):
    """Fetch fundamental data for a symbol from Yahoo Finance."""
    from packages.data.providers.base import FundamentalRequest
    req = FundamentalRequest(symbols=[symbol])
    fundamentals = list(yahoo.fundamentals(req))
    return [
        FundamentalResponse(
            symbol=f.symbol,
            taxonomy=f.taxonomy,
            period=f.period,
            value=float(f.value),
            unit=f.unit,
        )
        for f in fundamentals
    ]


# ── SEC EDGAR endpoints ────────────────────────────────────

@router.get("/sec/fundamentals/{symbol}", response_model=list[FundamentalResponse])
async def get_sec_fundamentals(
    symbol: str,
    _user: Any = Depends(get_current_user),
):
    """Fetch XBRL-tagged fundamentals from SEC EDGAR."""
    sec = SECEdgarProvider()
    from packages.data.providers.base import FundamentalRequest
    req = FundamentalRequest(symbols=[symbol])
    fundamentals = list(sec.fundamentals(req))
    return [
        FundamentalResponse(
            symbol=f.symbol,
            taxonomy=f.taxonomy,
            period=f.period,
            value=float(f.value),
            unit=f.unit,
        )
        for f in fundamentals[:50]  # Limit to 50 most recent
    ]


# ── Provider health ────────────────────────────────────────

@router.get("/providers/health", response_model=list[HealthResponse])
async def check_provider_health(
    _user: Any = Depends(get_current_user),
):
    """Check health of all data providers."""
    providers = [
        yahoo,
        SECEdgarProvider(),
    ]
    results = []
    for provider in providers:
        h = provider.health()
        results.append(HealthResponse(
            provider=h.name,
            status=h.status,
            error=h.error_message,
        ))
    return results
