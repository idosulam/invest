"""Instrument CRUD endpoints."""

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.auth import get_current_user, require_analyst
from apps.api.database import get_db
from packages.domain.entities.models import Instrument, User
from packages.domain.enums.common import InstrumentType, InstrumentStatus
from packages.data.providers.yahoo_finance import YahooFinanceProvider
from packages.data.ingestion.pipeline import IngestionPipeline
from packages.domain.enums.common import Timeframe

router = APIRouter(prefix="/instruments", tags=["instruments"])


# ── Schemas ─────────────────────────────────────────────────

class InstrumentCreate(BaseModel):
    symbol: str
    name: str
    type: InstrumentType
    venue_id: Optional[str] = None
    currency: str = "USD"
    isin: Optional[str] = None
    cusip: Optional[str] = None
    figi: Optional[str] = None
    exchange: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    country: Optional[str] = None


class InstrumentResponse(BaseModel):
    id: uuid.UUID
    symbol: str
    name: str
    type: InstrumentType
    venue_id: Optional[str]
    currency: str
    status: InstrumentStatus
    isin: Optional[str]
    cusip: Optional[str]
    figi: Optional[str]
    exchange: Optional[str]
    sector: Optional[str]
    industry: Optional[str]
    country: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class InstrumentListResponse(BaseModel):
    items: list[InstrumentResponse]
    total: int
    page: int
    page_size: int


# ── Endpoints ───────────────────────────────────────────────

@router.get("", response_model=InstrumentListResponse)
async def list_instruments(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    type: Optional[InstrumentType] = None,
    status: Optional[InstrumentStatus] = None,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """List instruments with filtering and pagination."""
    query = select(Instrument)
    count_query = select(func.count()).select_from(Instrument)

    if type:
        query = query.where(Instrument.type == type)
        count_query = count_query.where(Instrument.type == type)
    if status:
        query = query.where(Instrument.status == status)
        count_query = count_query.where(Instrument.status == status)
    if search:
        search_filter = Instrument.symbol.ilike(f"%{search}%") | Instrument.name.ilike(f"%{search}%")
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    total = (await db.execute(count_query)).scalar()
    offset = (page - 1) * page_size
    result = await db.execute(query.offset(offset).limit(page_size).order_by(Instrument.symbol))
    instruments = result.scalars().all()

    return InstrumentListResponse(
        items=[InstrumentResponse.model_validate(i) for i in instruments],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{instrument_id}", response_model=InstrumentResponse)
async def get_instrument(
    instrument_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Get a single instrument by ID."""
    result = await db.execute(select(Instrument).where(Instrument.id == instrument_id))
    instrument = result.scalar_one_or_none()
    if not instrument:
        raise HTTPException(status_code=404, detail="Instrument not found")
    return instrument


@router.post("", response_model=InstrumentResponse, status_code=status.HTTP_201_CREATED)
async def create_instrument(
    req: InstrumentCreate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_analyst),
):
    """Create a new instrument (analyst+ role required)."""
    # Check for duplicate symbol
    existing = await db.execute(
        select(Instrument).where(
            Instrument.symbol == req.symbol,
            Instrument.venue_id == req.venue_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Instrument with this symbol already exists")

    instrument = Instrument(**req.model_dump())
    db.add(instrument)
    await db.flush()
    await db.refresh(instrument)

    # Auto-ingest historical bars for the new instrument (best-effort;
    # failures here shouldn't block instrument creation).
    try:
        provider = YahooFinanceProvider()
        pipeline = IngestionPipeline(provider)
        await pipeline.ingest_bars(db, [instrument.symbol], Timeframe("1D"))
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning(
            f"Auto-ingestion failed for {instrument.symbol}: {exc}"
        )

    return instrument
