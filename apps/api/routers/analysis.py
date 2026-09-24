"""Analysis job endpoints (#5) — kick off background runs, poll, and last-run."""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.auth import get_current_user
from apps.api.database import get_db
from apps.api import jobs as jobmanager
from packages.domain.entities.models import Instrument, User
from packages.portfolio.context import list_portfolio_instrument_ids

router = APIRouter(prefix="/analysis", tags=["analysis"])

_MAX_INSTRUMENTS = 30


class RunRequest(BaseModel):
    scope: str = "portfolio"  # portfolio | discover | single
    instrument_id: Optional[uuid.UUID] = None
    target_weight: float = 0.05


@router.post("/run")
async def start_run(
    req: RunRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Start a background analysis run and return a job handle immediately."""
    scope = req.scope.lower()
    instrument_ids: list = []

    if scope == "single":
        if not req.instrument_id:
            raise HTTPException(status_code=400, detail="instrument_id required for scope=single")
        instrument_ids = [req.instrument_id]
    elif scope == "portfolio":
        instrument_ids = await list_portfolio_instrument_ids(db, user.id)
    elif scope == "discover":
        res = await db.execute(
            select(Instrument.id).where(Instrument.status == "ACTIVE").limit(_MAX_INSTRUMENTS)
        )
        instrument_ids = [row[0] for row in res.all()]
    else:
        raise HTTPException(status_code=400, detail=f"Unknown scope: {req.scope}")

    if not instrument_ids:
        raise HTTPException(status_code=400, detail=f"No instruments to analyze for scope={scope}")

    job = await jobmanager.start_analysis_job(scope, instrument_ids, user.id, req.target_weight)
    return {
        "job_id": job["job_id"],
        "job_name": job["job_name"],
        "status": job["status"],
        "started_at": job["started_at"],
        "scope": scope,
        "total": len(instrument_ids),
    }


@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str, _user: User = Depends(get_current_user)):
    job = jobmanager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/last-run")
async def get_last_run(
    scope: str = Query("portfolio"),
    _user: User = Depends(get_current_user),
):
    """Timestamp of the most recent analysis run — for the 'last run' badge."""
    return await jobmanager.last_run(scope)
