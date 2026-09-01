"""Watchlist CRUD endpoints — PRD Section 1.3 (watchlists, alerts)."""

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.auth import get_current_user
from apps.api.database import get_db
from packages.domain.entities.models import Watchlist, Instrument, User

router = APIRouter(prefix="/watchlists", tags=["watchlists"])


# ── Schemas ─────────────────────────────────────────────────

class WatchlistCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


class WatchlistUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)


class InstrumentRef(BaseModel):
    instrument_id: uuid.UUID


class WatchlistResponse(BaseModel):
    id: uuid.UUID
    name: str
    owner_id: uuid.UUID
    instrument_ids: list[uuid.UUID]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WatchlistListResponse(BaseModel):
    items: list[WatchlistResponse]
    total: int


class WatchlistDetailResponse(WatchlistResponse):
    """Watchlist with resolved instrument details."""
    instruments: list[dict] = []


# ── Endpoints ───────────────────────────────────────────────

@router.get("", response_model=WatchlistListResponse)
async def list_watchlists(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all watchlists owned by the current user."""
    result = await db.execute(
        select(Watchlist)
        .where(Watchlist.owner_id == current_user.id)
        .order_by(Watchlist.name)
    )
    watchlists = result.scalars().all()
    return WatchlistListResponse(
        items=[WatchlistResponse.model_validate(w) for w in watchlists],
        total=len(watchlists),
    )


@router.post("", response_model=WatchlistResponse, status_code=status.HTTP_201_CREATED)
async def create_watchlist(
    req: WatchlistCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new empty watchlist."""
    watchlist = Watchlist(
        name=req.name,
        owner_id=current_user.id,
        instrument_ids=[],
    )
    db.add(watchlist)
    await db.flush()
    await db.refresh(watchlist)
    return watchlist


@router.get("/{watchlist_id}", response_model=WatchlistDetailResponse)
async def get_watchlist(
    watchlist_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a watchlist with resolved instrument details."""
    result = await db.execute(
        select(Watchlist).where(
            Watchlist.id == watchlist_id,
            Watchlist.owner_id == current_user.id,
        )
    )
    watchlist = result.scalar_one_or_none()
    if not watchlist:
        raise HTTPException(status_code=404, detail="Watchlist not found")

    # Resolve instrument details
    instruments = []
    if watchlist.instrument_ids:
        inst_result = await db.execute(
            select(Instrument).where(Instrument.id.in_(watchlist.instrument_ids))
        )
        for inst in inst_result.scalars().all():
            instruments.append({
                "id": str(inst.id),
                "symbol": inst.symbol,
                "name": inst.name,
                "type": inst.type.value,
                "exchange": inst.exchange,
                "currency": inst.currency,
                "status": inst.status.value,
            })

    return WatchlistDetailResponse(
        **WatchlistResponse.model_validate(watchlist).model_dump(),
        instruments=instruments,
    )


@router.patch("/{watchlist_id}", response_model=WatchlistResponse)
async def update_watchlist(
    watchlist_id: uuid.UUID,
    req: WatchlistUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Rename a watchlist."""
    result = await db.execute(
        select(Watchlist).where(
            Watchlist.id == watchlist_id,
            Watchlist.owner_id == current_user.id,
        )
    )
    watchlist = result.scalar_one_or_none()
    if not watchlist:
        raise HTTPException(status_code=404, detail="Watchlist not found")

    if req.name is not None:
        watchlist.name = req.name

    await db.flush()
    await db.refresh(watchlist)
    return watchlist


@router.delete("/{watchlist_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_watchlist(
    watchlist_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a watchlist."""
    result = await db.execute(
        select(Watchlist).where(
            Watchlist.id == watchlist_id,
            Watchlist.owner_id == current_user.id,
        )
    )
    watchlist = result.scalar_one_or_none()
    if not watchlist:
        raise HTTPException(status_code=404, detail="Watchlist not found")

    await db.delete(watchlist)


@router.post("/{watchlist_id}/instruments", response_model=WatchlistResponse)
async def add_instrument(
    watchlist_id: uuid.UUID,
    ref: InstrumentRef,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add an instrument to a watchlist."""
    result = await db.execute(
        select(Watchlist).where(
            Watchlist.id == watchlist_id,
            Watchlist.owner_id == current_user.id,
        )
    )
    watchlist = result.scalar_one_or_none()
    if not watchlist:
        raise HTTPException(status_code=404, detail="Watchlist not found")

    # Validate instrument exists
    inst = await db.execute(select(Instrument).where(Instrument.id == ref.instrument_id))
    if not inst.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Instrument not found")

    ids = list(watchlist.instrument_ids or [])
    if ref.instrument_id not in [uuid.UUID(i) if isinstance(i, str) else i for i in ids]:
        ids.append(ref.instrument_id)
        watchlist.instrument_ids = ids

    await db.flush()
    await db.refresh(watchlist)
    return watchlist


@router.delete("/{watchlist_id}/instruments/{instrument_id}", response_model=WatchlistResponse)
async def remove_instrument(
    watchlist_id: uuid.UUID,
    instrument_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove an instrument from a watchlist."""
    result = await db.execute(
        select(Watchlist).where(
            Watchlist.id == watchlist_id,
            Watchlist.owner_id == current_user.id,
        )
    )
    watchlist = result.scalar_one_or_none()
    if not watchlist:
        raise HTTPException(status_code=404, detail="Watchlist not found")

    ids = list(watchlist.instrument_ids or [])
    ids = [uuid.UUID(i) if isinstance(i, str) else i for i in ids]
    if instrument_id in ids:
        ids.remove(instrument_id)
        watchlist.instrument_ids = ids

    await db.flush()
    await db.refresh(watchlist)
    return watchlist
